from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import faiss
import numpy as np
from interview_ai.cv.profile_extractor import (
    CandidateInfo,
    extract_candidate_info,
    extract_text_from_cv,
    normalize_cv_text,
)

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

SessionId = str

@dataclass(frozen=True)
class SearchCandidate:
    chunk_index: int
    semantic_score: float = 0.0
    semantic_rank: int = 0

BEHAVIORAL_HINTS = frozenset({
    "situation", "exemple", "collaboration", "conflit", "equipe", "équipe",
    "team", "client", "gestion", "probleme", "problème", "difficulte",
    "difficulté", "resultat", "résultat",
})

MOTIVATION_HINTS = frozenset({
    "motivation", "pourquoi", "poste", "entreprise", "interesse", "intéressé",
    "objectif", "projet", "avenir", "carriere", "carrière", "souhaite", "rejoindre",
})

STOPWORDS = frozenset({
    "avec", "dans", "pour", "vous", "quoi", "comment", "quel", "quelle",
    "quelles", "quels", "etre", "être", "avoir", "chez", "poste", "projet",
    "cette", "cela", "plus", "tres", "très", "une", "des", "les", "and", "sur",
    "par", "aux", "ses", "son", "est", "sont", "mais", "du", "de", "la",
})

SIMPLE_STEM = {
    "developpeur": "dev",
    "developpeuse": "dev",
    "développeur": "dev",
    "développeuse": "dev",
    "developer": "dev",
    "developpement": "dev",
    "développement": "dev",
    "experience": "exp",
    "experiences": "exp",
    "expérience": "exp",
    "expériences": "exp",
    "formation": "form",
    "formations": "form",
    "education": "form",
    "competence": "skill",
    "competences": "skill",
    "compétence": "skill",
    "compétences": "skill",
    "skills": "skill",
    "projet": "proj",
    "projets": "proj",
    "project": "proj",
    "ingenieur": "ing",
    "ingénieur": "ing",
    "engineer": "ing",
    "architecte": "arch",
}

SECTION_PATTERN = re.compile(
    r"^(Experience|Expérience|Experiences|Expériences|Parcours professionnel|"
    r"Formation|Formations|Education|Éducation|Competences|Compétences|Skills|"
    r"Langues|Projets|Certifications|Centres?\s*d['’]?(interet|intérêt)|"
    r"Loisirs|Informations complementaires|Informations complémentaires)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)

class CVRAGStore:
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        chunk_size: int = 480,
        chunk_overlap: int = 100,
        embed_batch_size: int = 64,
        retrieval_multiplier: int = 3,
        session_ttl_minutes: int = 120,
    ) -> None:
        if chunk_size <= 0 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("chunk_size / overlap invalides")

        self.model_name = model_name
        self.model: "SentenceTransformer | None" = None
        self.dim = 384

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embed_batch_size = embed_batch_size
        self.retrieval_multiplier = max(1, retrieval_multiplier)
        self.session_ttl = timedelta(minutes=max(1, session_ttl_minutes))

        self._sessions: dict[SessionId, dict[str, Any]] = {}
        self._last_access: dict[SessionId, datetime] = {}

    def _get_model(self) -> SentenceTransformer:
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self.model = SentenceTransformer(self.model_name)
                self.dim = self.model.get_sentence_embedding_dimension()
            except Exception as exc:
                raise RuntimeError(f"Echec chargement modele {self.model_name}") from exc
        return self.model

    def _extract_chunks(self, filename: str, content: bytes) -> tuple[str, list[str]]:
        raw_text = extract_text_from_cv(filename, content, logger=logger)
        clean_text = normalize_cv_text(raw_text)

        if not clean_text:
            raise ValueError("Aucun texte extrait du document")

        chunks = self._smart_chunk(clean_text)
        if not chunks:
            raise ValueError("Aucun chunk valide")
        return clean_text, chunks

    def _store_session_payload(
        self,
        session_id: SessionId,
        *,
        cv_chunks: list[str] | None = None,
        cv_embeddings: np.ndarray | None = None,
        document_chunks: list[str] | None = None,
        document_embeddings: np.ndarray | None = None,
        profile: CandidateInfo | dict[str, Any] | None = None,
        documents: list[dict[str, Any]] | None = None,
    ) -> None:
        resolved_cv_chunks = list(cv_chunks or [])
        resolved_document_chunks = list(document_chunks or [])
        resolved_cv_embeddings = (
            cv_embeddings
            if isinstance(cv_embeddings, np.ndarray) and cv_embeddings.size
            else np.empty((0, self.dim), dtype=np.float32)
        )
        resolved_document_embeddings = (
            document_embeddings
            if isinstance(document_embeddings, np.ndarray) and document_embeddings.size
            else np.empty((0, self.dim), dtype=np.float32)
        )

        chunks = resolved_cv_chunks + resolved_document_chunks
        embeddings = (
            np.vstack([resolved_cv_embeddings, resolved_document_embeddings])
            if resolved_cv_embeddings.size and resolved_document_embeddings.size
            else resolved_cv_embeddings
            if resolved_cv_embeddings.size
            else resolved_document_embeddings
        )
        index = self._build_index(embeddings) if embeddings.size else faiss.IndexFlatIP(self.dim)
        self._sessions[session_id] = {
            "chunks": chunks,
            "embeddings": embeddings,
            "index": index,
            "cv_chunks": resolved_cv_chunks,
            "cv_embeddings": resolved_cv_embeddings,
            "document_chunks": resolved_document_chunks,
            "document_embeddings": resolved_document_embeddings,
            "profile": profile or {},
            "documents": list(documents or []),
        }
        self._touch(session_id)

    def _touch(self, sid: SessionId) -> None:
        self._last_access[sid] = datetime.now()

    def expire_old_sessions(self) -> list[SessionId]:
        now = datetime.now()
        expired = [
            sid for sid, ts in self._last_access.items()
            if now - ts > self.session_ttl
        ]
        for sid in expired:
            self.clear_session(sid)
        return expired

    def clear_session(self, sid: SessionId) -> None:
        self._sessions.pop(sid, None)
        self._last_access.pop(sid, None)
        logger.info("Session supprimee : %s", sid)

    def ingest_cv(self, session_id: SessionId, filename: str, content: bytes) -> dict[str, Any]:
        self.expire_old_sessions()
        clean_text, chunks = self._extract_chunks(filename, content)

        profile = extract_candidate_info(clean_text, filename)
        cv_embeddings = self._embed_chunks(chunks)
        existing_session = self._sessions.get(session_id) or {}
        existing_documents = self.get_documents(session_id)
        self._store_session_payload(
            session_id,
            cv_chunks=chunks,
            cv_embeddings=cv_embeddings,
            document_chunks=list(existing_session.get("document_chunks", [])),
            document_embeddings=existing_session.get("document_embeddings"),
            profile=profile,
            documents=existing_documents,
        )

        logger.info("CV ingere - session=%s | chunks=%d", session_id, len(chunks))

        return {
            "filename": filename,
            "chunk_count": len(chunks),
            "profile": profile.__dict__,
            "status": "ingested",
        }

    def ingest_document(self, session_id: SessionId, filename: str, content: bytes) -> dict[str, Any]:
        self.expire_old_sessions()
        _, chunks = self._extract_chunks(filename, content)
        new_document_embeddings = self._embed_chunks(chunks)

        existing_session = self._sessions.get(session_id)
        existing_document_chunks = list(existing_session.get("document_chunks", [])) if existing_session else []
        existing_document_embeddings = existing_session.get("document_embeddings") if existing_session else None
        existing_profile = existing_session.get("profile", {}) if existing_session else {}
        existing_documents = self.get_documents(session_id)

        combined_document_chunks = existing_document_chunks + chunks
        if isinstance(existing_document_embeddings, np.ndarray) and existing_document_embeddings.size:
            combined_document_embeddings = np.vstack([existing_document_embeddings, new_document_embeddings])
        else:
            combined_document_embeddings = new_document_embeddings

        document_record = {
            "filename": filename,
            "chunk_count": len(chunks),
            "status": "ingested",
        }
        self._store_session_payload(
            session_id,
            cv_chunks=list(existing_session.get("cv_chunks", [])) if existing_session else [],
            cv_embeddings=existing_session.get("cv_embeddings") if existing_session else None,
            document_chunks=combined_document_chunks,
            document_embeddings=combined_document_embeddings,
            profile=existing_profile,
            documents=existing_documents + [document_record],
        )

        logger.info(
            "Document technique ingere - session=%s | filename=%s | chunks=%d",
            session_id,
            filename,
            len(chunks),
        )

        return {
            "filename": filename,
            "chunk_count": len(chunks),
            "documents": self.get_documents(session_id),
            "status": "ingested",
        }

    def retrieve_context(self, session_id: SessionId, query: str, top_k: int = 5) -> list[str]:
        session = self._sessions.get(session_id)
        if session is None:
            logger.info("Session inconnue : %s", session_id)
            return []

        self._touch(session_id)

        chunks = session["chunks"]
        top_k = max(1, min(top_k, len(chunks)))
        pool_size = min(len(chunks), top_k * self.retrieval_multiplier)

        query_emb = self._encode(query)
        semantic_hits = self._semantic_search(session, query_emb, pool_size)
        if not semantic_hits:
            return []

        reranked = self._rerank(
            session=session,
            query=query,
            query_emb=query_emb,
            candidates=semantic_hits,
        )
        return [chunks[candidate.chunk_index] for candidate in reranked[:top_k]]

    def retrieve_document_context(self, session_id: SessionId, query: str, top_k: int = 5) -> list[str]:
        session = self._sessions.get(session_id)
        if session is None:
            logger.info("Session inconnue : %s", session_id)
            return []

        self._touch(session_id)
        chunks = list(session.get("document_chunks", []) or [])
        embeddings = session.get("document_embeddings")
        if not chunks or not isinstance(embeddings, np.ndarray) or not embeddings.size:
            return []

        top_k = max(1, min(top_k, len(chunks)))
        pool_size = min(len(chunks), top_k * self.retrieval_multiplier)
        query_emb = self._encode(query)

        document_session = {
            "chunks": chunks,
            "embeddings": embeddings,
            "index": self._build_index(embeddings),
        }
        semantic_hits = self._semantic_search(document_session, query_emb, pool_size)
        reranked = self._rerank(
            session=document_session,
            query=query,
            query_emb=query_emb,
            candidates=semantic_hits,
        )
        return [chunks[candidate.chunk_index] for candidate in reranked[:top_k]]

    def get_profile(self, session_id: SessionId) -> CandidateInfo | dict[str, Any]:
        session = self._sessions.get(session_id)
        if session is None:
            return {}
        self._touch(session_id)
        return session["profile"]

    def get_documents(self, session_id: SessionId) -> list[dict[str, Any]]:
        session = self._sessions.get(session_id)
        if session is None:
            return []
        self._touch(session_id)
        documents = session.get("documents", [])
        return [dict(item) for item in documents if isinstance(item, dict)]

    def _encode(self, text: str) -> np.ndarray:
        embedding = self._get_model().encode(text, normalize_embeddings=True)
        return np.asarray(embedding, dtype=np.float32).reshape(1, -1)

    def _embed_chunks(self, chunks: list[str]) -> np.ndarray:
        embeddings = self._get_model().encode(
            chunks,
            batch_size=self.embed_batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(embeddings, dtype=np.float32)

    def _build_index(self, embeddings: np.ndarray) -> faiss.Index:
        index = faiss.IndexFlatIP(self.dim)
        index.add(embeddings)
        return index

    def _semantic_search(
        self,
        session: dict[str, Any],
        q_emb: np.ndarray,
        k: int,
    ) -> list[SearchCandidate]:
        index: faiss.Index = session["index"]
        scores, ids = index.search(q_emb, k)

        return [
            SearchCandidate(
                chunk_index=int(idx),
                semantic_score=float(score),
                semantic_rank=rank + 1,
            )
            for rank, (idx, score) in enumerate(zip(ids[0], scores[0]))
            if 0 <= idx < len(session["chunks"])
        ]

    def _rerank(
        self,
        *,
        session: dict[str, Any],
        query: str,
        query_emb: np.ndarray,
        candidates: list[SearchCandidate],
    ) -> list[SearchCandidate]:
        if not candidates:
            return []

        chunks = session["chunks"]
        embeddings = session["embeddings"]
        query_tokens = self._tokenize(query)
        query_lower = query.lower()

        scored: list[tuple[float, SearchCandidate]] = []

        for candidate in candidates:
            idx = candidate.chunk_index
            chunk = chunks[idx]
            chunk_vec = embeddings[idx].reshape(1, -1)

            cos_sim = float(np.dot(query_emb, chunk_vec.T)[0][0])
            cos_norm = (cos_sim + 1) / 2

            lexical = self._lexical_score(query_tokens, chunk)
            phrase = self._phrase_score(query, chunk)
            domain = self._domain_bonus(query_lower, chunk.lower())

            final_score = (
                cos_norm * 0.72 +
                lexical * 0.14 +
                phrase * 0.08 +
                domain * 0.06
            )
            scored.append((final_score, candidate))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [candidate for _, candidate in scored]

    def _lexical_score(self, query_tokens: set[str], chunk: str) -> float:
        if not query_tokens:
            return 0.0
        chunk_tokens = self._tokenize(chunk)
        return len(query_tokens & chunk_tokens) / len(query_tokens)

    def _phrase_score(self, query: str, chunk: str) -> float:
        terms = re.findall(r"[A-Za-zÀ-ÿ]{4,}", query.lower())
        if not terms:
            return 0.0
        chunk_lower = chunk.lower()
        return sum(term in chunk_lower for term in terms) / len(terms)

    def _domain_bonus(self, query_lower: str, chunk_lower: str) -> float:
        bonus = 0.0
        if any(hint in query_lower for hint in BEHAVIORAL_HINTS) and any(hint in chunk_lower for hint in BEHAVIORAL_HINTS):
            bonus += 0.5
        if any(hint in query_lower for hint in MOTIVATION_HINTS) and any(hint in chunk_lower for hint in MOTIVATION_HINTS):
            bonus += 0.5
        return bonus

    def _smart_chunk(self, text: str) -> list[str]:
        chunks: list[str] = []
        for section in self._split_sections(text):
            chunks.extend(self._chunk_section(section))
        return [chunk.strip() for chunk in chunks if len(chunk.strip()) >= 40]

    def _split_sections(self, text: str) -> list[str]:
        lines = [line.strip() for line in text.splitlines()]
        sections: list[str] = []
        current: list[str] = []

        for line in lines:
            if not line:
                continue
            if SECTION_PATTERN.match(line):
                if current:
                    sections.append("\n".join(current).strip())
                current = [line]
            else:
                current.append(line)

        if current:
            sections.append("\n".join(current).strip())

        return [section for section in sections if section]

    def _chunk_section(self, text: str) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text]

        chunks: list[str] = []
        current = ""

        for sentence in re.split(r"(?<=[\.\!\?\:])\s+", text):
            sentence = sentence.strip()
            if not sentence:
                continue

            candidate = f"{current} {sentence}".strip() if current else sentence
            if len(candidate) <= self.chunk_size:
                current = candidate
                continue

            if current:
                chunks.append(current)

            if len(sentence) <= self.chunk_size:
                current = sentence
            else:
                chunks.extend(self._split_long_sentence(sentence))
                current = ""

        if current:
            chunks.append(current)

        return chunks

    def _split_long_sentence(self, sentence: str) -> list[str]:
        pieces: list[str] = []
        start = 0

        while start < len(sentence):
            end = min(start + self.chunk_size, len(sentence))
            piece = sentence[start:end].strip()
            if piece:
                pieces.append(piece)
            if end >= len(sentence):
                break
            start = end - self.chunk_overlap

        return pieces

    def _tokenize(self, text: str) -> set[str]:
        words = re.findall(r"[A-Za-zÀ-ÿ]{3,}", text.lower())
        return {
            SIMPLE_STEM.get(word, word)
            for word in words
            if word not in STOPWORDS
        }

if __name__ == "__main__":
    print("Module CV RAG - version restructuree")
