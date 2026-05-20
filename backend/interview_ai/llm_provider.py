from __future__ import annotations

import logging
import re
import time
import unicodedata
from typing import Any

from openai import APIConnectionError

from interview_ai.base import Intelligence, LLMRateLimitError
from interview_ai.constants import MAX_EVIDENCE_CHARS, MAX_NOTES, SKILL_KEYS, VALID_PHASES
from interview_ai.payloads import normalize_llm_payload
from interview_ai.prompts import (
    build_cv_anchor_terms,
    build_cv_summary,
    build_generation_messages,
    build_rephrase_messages,
    build_repair_instruction,
    detect_response_language,
    normalize_cv_profile,
)
from interview_ai.scoring import infer_competencies_from_interview as infer_scores_payload
from interview_ai.scoring import score_interview_turn as score_turn_payload
from reporting.insights_builder import generate_insights_advice_text as generate_insights_advice_payload
from reporting.report_builder import generate_final_report_text as generate_report_payload

logger = logging.getLogger(__name__)


class StructuredInterviewIntelligence(Intelligence):
    """Shared technical interview intelligence pipeline for structured LLM transports."""

    DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
    DEFAULT_MODEL = "openai/gpt-oss-20b"
    VALID_PHASES = VALID_PHASES
    SKILL_KEYS = SKILL_KEYS
    MAX_EVIDENCE_CHARS = MAX_EVIDENCE_CHARS
    MAX_NOTES = MAX_NOTES

    @classmethod
    def resolve_transport_config(
        cls,
        *,
        base_url: str,
        model: str,
    ) -> tuple[str, str]:
        resolved_base_url = (base_url or cls.DEFAULT_BASE_URL).strip().rstrip("/")
        resolved_model = (model or cls.DEFAULT_MODEL).strip()
        return resolved_base_url, resolved_model

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        transport: Any,
        provider_name: str,
        temperature: float = 0.6,
        max_tokens: int = 900,
        base_url: str = "",
    ) -> None:
        resolved_api_key = (api_key or "").strip()
        if not resolved_api_key:
            raise RuntimeError("LLM_API_KEY missing in configuration")

        self.api_key = resolved_api_key
        self.base_url = (base_url or "").strip().rstrip("/")
        self.model = (model or "openai/gpt-oss-20b").strip()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.provider_name = (provider_name or "llm").strip().lower()
        self.transport = transport

    def _resolve_temperature(self, phase: str, override: float | None = None) -> float:
        temp = override if override is not None else self.temperature
        if phase == "FINAL":
            return 0.15
        if phase in ("QUESTION_3", "QUESTION_4"):
            return 0.35
        return temp

    @staticmethod
    def _is_technical_question_phase(phase: str) -> bool:
        return str(phase or "").upper().startswith("QUESTION_")

    @staticmethod
    def _content_tokens(text: str) -> set[str]:
        stopwords = {
            "question", "cours", "candidat", "candidate", "comment", "pourquoi",
            "expliquez", "expliquer", "decrire", "decrivez", "quelle", "quelles",
            "quels", "dans", "avec", "pour", "vous", "votre", "peux", "peut",
            "what", "why", "how", "explain", "describe", "course", "answer",
        }
        folded = unicodedata.normalize("NFKD", str(text or "").lower())
        folded = "".join(char for char in folded if not unicodedata.combining(char))
        normalized = re.sub(r"[^A-Za-z0-9]+", " ", folded)
        return {
            token
            for token in normalized.split()
            if len(token) >= 5 and token not in stopwords
        }

    @staticmethod
    def _clean_course_reference_phrasing(question: str) -> str:
        cleaned = " ".join(str(question or "").split()).strip()
        cleaned = re.sub(
            r"\s+(?:telle|tel|comme)\s+qu.*$",
            "?",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\s+selon\s+(?:le\s+)?(?:cours|chapitre|document|pdf|support).*$",
            "?",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\s+(?:dans|du|de)\s+(?:le\s+)?chapitre\s+\d+.*$",
            "?",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s+:", ":", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        return cleaned

    def _validate_technical_question(
        self,
        *,
        question: str,
        recent_turns: list[dict[str, Any]],
        phase: str = "",
        expected_language: str = "fr",
        cv_profile: dict[str, Any] | None = None,
        cv_context: list[str] | None = None,
    ) -> str:
        normalized = self._clean_course_reference_phrasing(question)
        if not normalized:
            raise ValueError("question technique vide")
        if not normalized.endswith("?"):
            normalized = f"{normalized.rstrip('.!')}?"
        if len(normalized) < 12:
            raise ValueError("question technique trop courte")

        if str(expected_language or "").strip().lower() == "fr" and detect_response_language(normalized) == "en":
            raise ValueError("question generee en anglais pour une session francaise")
        if str(expected_language or "").strip().lower() == "en" and detect_response_language(normalized) == "fr":
            raise ValueError("question generated in French for an English session")

        lowered = normalized.lower()
        placeholder_surface = re.sub(r"[^a-z0-9]+", " ", lowered).strip()
        if placeholder_surface in {
            "une seule question technique",
            "question technique concrete basee sur le cv",
            "question technique basee sur le cv",
            "one technical question",
            "concrete technical question based on the cv",
        }:
            raise ValueError("question placeholder non concrete")
        if len(self._content_tokens(normalized)) <= 1 and any(
            marker in placeholder_surface
            for marker in ("question technique", "technical question")
        ):
            raise ValueError("question technique trop generique")

        previous_questions = [
            " ".join(str(turn.get("say", "") or "").split()).strip().lower()
            for turn in recent_turns[-5:]
            if isinstance(turn, dict)
        ]
        if lowered in previous_questions:
            raise ValueError("question technique repetee")

        profile = normalize_cv_profile(cv_profile or {})
        phase_name = str(phase or "").upper()
        is_cv_question = phase_name == "QUESTION_1"
        if is_cv_question:
            candidate_name = str(profile.get("candidate_name") or profile.get("name") or "").strip().lower()
            if candidate_name:
                name_parts = [part for part in re.split(r"\s+", candidate_name) if len(part) >= 3]
                if not any(part in lowered for part in name_parts):
                    raise ValueError("question CV sans salutation nominative")
        profile_context_parts = [
            build_cv_summary(profile),
            " ".join(build_cv_anchor_terms(profile, cv_context or [])[:12]),
        ]
        course_context = " ".join(str(chunk or "") for chunk in list(cv_context or [])[:6])
        source_context = (
            " ".join([*(str(part or "") for part in profile_context_parts), course_context])
            if is_cv_question
            else course_context
        )
        if not source_context.strip():
            raise ValueError("aucun contexte CV ou cours disponible" if is_cv_question else "aucun passage de cours disponible")
        question_terms = self._content_tokens(normalized)
        source_terms = self._content_tokens(source_context)
        if question_terms and not (question_terms & source_terms):
            if is_cv_question and build_cv_anchor_terms(profile, cv_context or []):
                logger.info(
                    "Question acceptee avec faible recouvrement lexical mais CV disponible: %s",
                    normalized,
                )
                return normalized
            raise ValueError("question hors contexte CV/cours" if is_cv_question else "question hors contenu du cours")
        return normalized

    def _build_cv_grounded_fallback_question(
        self,
        *,
        lang: str,
        cv_profile: dict[str, Any],
        cv_context: list[str],
        recent_turns: list[dict[str, Any]],
    ) -> str:
        profile = normalize_cv_profile(cv_profile or {})
        preferred_anchors = [
            *(str(item).strip() for item in profile.get("projects", []) if str(item).strip()),
            *(str(item).strip() for item in profile.get("top_skills", []) if str(item).strip()),
            *(str(item).strip() for item in profile.get("experiences", []) if str(item).strip()),
        ]
        anchors = [*preferred_anchors, *build_cv_anchor_terms(profile, cv_context or [])]
        used_questions = " ".join(str(turn.get("say", "") or "").lower() for turn in recent_turns[-5:])
        anchor = next((item for item in anchors if item.lower() not in used_questions), "")
        if not anchor:
            skills = [str(item).strip() for item in profile.get("top_skills", []) if str(item).strip()]
            anchor = skills[0] if skills else str(profile.get("headline", "") or "").strip()
        if not anchor:
            anchor = "un projet technique mentionne dans votre CV" if lang != "en" else "a technical project from your CV"
        candidate_name = str(profile.get("candidate_name") or profile.get("name") or "").strip()

        if lang == "en":
            greeting = f"Hello {candidate_name}, " if candidate_name else "Hello, "
            return (
                f"{greeting}in your CV, you mention {anchor}. Can you explain one concrete technical decision "
                "you made around it and why?"
            )
        greeting = f"Bonjour {candidate_name}, " if candidate_name else "Bonjour, "
        return (
            f"{greeting}dans votre CV, vous mentionnez {anchor}. Pouvez-vous expliquer un choix technique concret "
            "que vous avez fait autour de cet element et pourquoi ?"
        )

    def _build_course_grounded_fallback_question(
        self,
        *,
        lang: str,
        phase: str,
        cv_context: list[str],
        recent_turns: list[dict[str, Any]],
    ) -> str:
        used_questions = " ".join(str(turn.get("say", "") or "").lower() for turn in recent_turns[-5:])
        context = " ".join(str(chunk or "") for chunk in list(cv_context or [])[:4])
        sentences = [item.strip(" -:;,.") for item in re.split(r"(?<=[.!?])\s+|[;\n]", context) if item.strip()]
        anchor = next((item for item in sentences if len(item) >= 25 and item.lower()[:70] not in used_questions), "")
        if len(anchor) > 140:
            anchor = anchor[:137].rstrip(" ,;:.") + "..."

        phase_name = str(phase or "").upper()
        if lang == "en":
            if anchor:
                return f"Based on the course, can you explain this concept in your own words: {anchor}?"
            return "Can you explain one key concept from the course and give its technical role?"

        if anchor:
            if phase_name == "QUESTION_4":
                return f"A partir du cours, pouvez-vous synthetiser le role technique de cette notion : {anchor} ?"
            return f"D'apres le cours, pouvez-vous expliquer avec vos mots cette notion technique : {anchor} ?"
        return "Pouvez-vous expliquer une notion technique centrale du cours et son role ?"

    def _request_json(
        self,
        *,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        log_mode: str,
        phase: str,
    ) -> dict[str, Any]:
        return self.transport.request_json(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            log_mode=log_mode,
            phase=phase,
        )

    def _call_model(
        self,
        messages: list[dict[str, str]],
        *,
        phase: str,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        return self._request_json(
            messages=messages,
            max_tokens=max(700, self.max_tokens),
            temperature=self._resolve_temperature(phase, temperature),
            log_mode="prompt_json",
            phase=phase,
        )

    def _compute_retry_temperature(self, reason: str, base_retry_temp: float) -> float:
        if "repetee" in reason:
            return max(base_retry_temp, self.temperature + 0.1)
        if "trop technique" in reason:
            return max(base_retry_temp, self.temperature + 0.05)
        return max(base_retry_temp, self.temperature)

    def _normalize_competency_scores(self, value: Any) -> dict[str, int]:
        scores: dict[str, int] = {}
        raw = value if isinstance(value, dict) else {}
        for key in self.SKILL_KEYS:
            try:
                scores[key] = max(0, min(5, int(raw.get(key, 0))))
            except Exception:
                scores[key] = 0
        return scores

    def _empty_skills_payload(self) -> dict[str, dict[str, Any]]:
        return {}

    def _empty_score_payload(self) -> dict[str, int]:
        return {key: 0 for key in self.SKILL_KEYS}

    def _build_rephrase_payload(
        self,
        *,
        session_id: str,
        candidate_name: str,
        phase: str,
        lang: str,
        text: str,
        question_to_rephrase: str,
        question_index: int,
        cv_profile: dict[str, Any],
        cv_context: list[str],
        recent_turns: list[dict[str, Any]],
    ) -> dict[str, Any]:
        messages = build_rephrase_messages(
            session_id=session_id,
            candidate_name=candidate_name,
            phase=phase,
            lang=lang,
            clarification_text=text,
            original_question=question_to_rephrase,
            question_index=question_index,
            recent_turns=recent_turns,
            cv_profile=cv_profile,
            rag_context=cv_context,
        )

        parsed = normalize_llm_payload(
            self._call_model(messages, phase=phase, temperature=0.2),
            phase,
            max(0, question_index - 1),
        )
        if self._is_technical_question_phase(phase):
            parsed["say"] = self._validate_technical_question(
                question=str(parsed.get("say", "")).strip(),
                recent_turns=recent_turns[:-1] if recent_turns else [],
                phase=phase,
                expected_language=lang,
                cv_profile=cv_profile,
                cv_context=cv_context,
            )
        else:
            parsed["say"] = str(parsed.get("say", "")).strip()
        parsed["phase"] = phase
        parsed["question_index"] = question_index
        parsed["score_partial"] = self._empty_score_payload()
        parsed["notes"] = ["reformulation"]
        parsed["final_report"] = None
        return parsed

    def _resolve_turn_scoring_context(
        self,
        *,
        text: str,
        phase: str,
        recent_turns: list[dict[str, Any]],
    ) -> tuple[str, str]:
        if not recent_turns:
            return "", "QUESTION_1"

        last_turn = recent_turns[-1] if isinstance(recent_turns[-1], dict) else {}
        question = str(last_turn.get("say", "") or "").strip()
        question_phase = str(last_turn.get("phase", "") or phase).strip().upper() or phase
        if phase == "FINAL" and len(recent_turns) >= 1:
            question_phase = str(last_turn.get("phase", "") or "QUESTION_4").strip().upper() or "QUESTION_4"
        if not question and text:
            return "", question_phase
        return question, question_phase

    def _apply_turn_scoring(
        self,
        *,
        parsed: dict[str, Any],
        text: str,
        phase: str,
        lang: str,
        cv_profile: dict[str, Any],
        cv_context: list[str],
        recent_turns: list[dict[str, Any]],
    ) -> dict[str, Any]:
        question, question_phase = self._resolve_turn_scoring_context(
            text=text,
            phase=phase,
            recent_turns=recent_turns,
        )
        scoring_payload = self.score_interview_turn(
            cv_profile=cv_profile,
            recent_turns=recent_turns,
            question=question,
            answer=text,
            question_phase=question_phase,
            response_language=lang,
        )
        parsed["score_partial"] = self._normalize_competency_scores(scoring_payload.get("score_partial"))
        parsed.pop("skills", None)
        return parsed

    def _build_phase_retry_messages(
        self,
        *,
        messages: list[dict[str, str]],
        phase: str,
        lang: str,
        reason: str,
        last_question: str,
    ) -> tuple[list[dict[str, str]], float]:
        instruction, base_retry_temp = build_repair_instruction(reason)
        retry_messages = messages + [
            {
                "role": "user",
                "content": (
                    f"Question rejetee: {last_question or '[vide]'}. "
                    f"Motif de rejet: {reason}. "
                    f"{instruction}"
                ),
            }
        ]

        if phase == "BEHAVIOR" and "behavior trop detaillee" in reason:
            retry_messages.append(
                {
                    "role": "user",
                    "content": (
                        "Consigne BEHAVIOR stricte : pars d'un projet ou d'une experience du CV. "
                        "Demande un defi, une difficulte, un probleme ou une situation concrete. "
                        "N'ecris pas une question centree sur API, Spring Boot, React, composant, endpoint ou repository."
                    ),
                }
            )
        if phase == "BEHAVIOR" and "behavior trop affirmative" in reason:
            retry_messages.append(
                {
                    "role": "user",
                    "content": (
                        "Consigne BEHAVIOR stricte : ne formule pas 'une situation ou vous avez du gerer...'. "
                        "Utilise une forme plus neutre et exploratoire, par exemple : "
                        "'Avez-vous un exemple concret de... ?' ou "
                        "'Sur l'un de vos projets, avez-vous deja ete confronte(e) a... ?'. "
                        "Exemple valide : 'Sur l'un de vos projets, avez-vous deja ete confronte(e) a un conflit d'opinion dans l'equipe ?'."
                    ),
                }
            )

        if phase == "INTRO" and "intro invalide" in reason:
            intro_retry_content = (
                "Consigne INTRO stricte : commence par une courte phrase de bienvenue ou de remerciement, "
                "puis pose une seule question large sur le parcours, "
                "le background ou ce qui motive la personne dans son travail. "
                "Utilise seulement le nom du candidat et le headline. "
                "Ne mentionne ni projet, ni entreprise, ni annees d'experience."
            )
            if lang == "en":
                intro_retry_content = (
                    "Strict INTRO instruction: start with a short welcome or thank-you sentence, "
                    "then ask one broad opening question about the candidate's "
                    "background or what motivates them in their work. "
                    "Use only the candidate's name and headline. "
                    "Do not mention a project, a company, an internship, or years of experience."
                )
            retry_messages.append({"role": "user", "content": intro_retry_content})

        if self._is_technical_question_phase(phase):
            phase_name = str(phase or "").upper()
            phase_instruction = (
                "Consigne technique stricte : pose une seule question technique courte et concrete sur le CV. "
                "Commence par Bonjour + nom du candidat. "
                "La question doit mentionner une competence, un projet, une experience ou une technologie du CV."
                if phase_name == "QUESTION_1"
                else
                "Consigne technique stricte : pose une seule question technique courte et concrete strictement basee sur le cours. "
                "Ne mentionne pas le CV, les projets, les experiences ou la motivation du candidat."
            )
            retry_messages.append(
                {
                    "role": "user",
                    "content": f"{phase_instruction} N'ecris jamais une phrase placeholder comme 'une seule question technique'.",
                }
            )

        return retry_messages, base_retry_temp

    def _validate_or_repair_question(
        self,
        *,
        parsed: dict[str, Any],
        messages: list[dict[str, str]],
        phase: str,
        lang: str,
        text: str,
        cv_profile: dict[str, Any],
        cv_context: list[str],
        recent_turns: list[dict[str, Any]],
        session_id: str,
        total_start: float,
        last_index: int,
    ) -> dict[str, Any]:
        last_reason = "invalide"

        for _ in range(3):
            try:
                candidate_question = str(parsed.get("say", "")).strip()
                if self._is_technical_question_phase(phase):
                    parsed["say"] = self._validate_technical_question(
                        question=candidate_question,
                        recent_turns=recent_turns,
                        phase=phase,
                        expected_language=lang,
                        cv_profile=cv_profile,
                        cv_context=cv_context,
                    )
                else:
                    parsed["say"] = candidate_question
                logger.info(
                    "LLM generate session_id=%s phase=%s provider=%s total_ms=%.1f recent_turns=%d cv_context=%d",
                    session_id,
                    phase,
                    self.provider_name,
                    (time.perf_counter() - total_start) * 1000,
                    len(recent_turns),
                    len(cv_context),
                )
                return parsed
            except ValueError as exc:
                reason = str(exc).lower()
                last_reason = reason
                last_question = str(parsed.get("say", "")).strip()
                logger.warning(
                    "Question LLM rejetee session_id=%s phase=%s provider=%s reason=%s question=%s",
                    session_id,
                    phase,
                    self.provider_name,
                    reason,
                    last_question,
                )
                retry_messages, base_retry_temp = self._build_phase_retry_messages(
                    messages=messages,
                    phase=phase,
                    lang=lang,
                    reason=reason,
                    last_question=last_question,
                )
                parsed = normalize_llm_payload(
                    self._call_model(
                        retry_messages,
                        phase=phase,
                        temperature=self._compute_retry_temperature(reason, base_retry_temp),
                    ),
                    phase,
                    last_index,
                )

        if str(phase or "").upper() == "QUESTION_1":
            fallback_question = self._build_cv_grounded_fallback_question(
                lang=lang,
                cv_profile=cv_profile,
                cv_context=cv_context,
                recent_turns=recent_turns,
            )
        else:
            fallback_question = self._build_course_grounded_fallback_question(
                lang=lang,
                phase=phase,
                cv_context=cv_context,
                recent_turns=recent_turns,
            )
        parsed["say"] = fallback_question
        parsed["phase"] = phase
        parsed["question_index"] = max(1, last_index + 1)
        parsed["score_partial"] = self._empty_score_payload()
        parsed["notes"] = [
            *(parsed.get("notes") if isinstance(parsed.get("notes"), list) else []),
            f"Question de secours ancree CV apres rejet: {last_reason}",
        ][: self.MAX_NOTES]
        logger.warning(
            "Question LLM remplacee par fallback CV session_id=%s phase=%s provider=%s reason=%s question=%s",
            session_id,
            phase,
            self.provider_name,
            last_reason,
            fallback_question,
        )
        return parsed

    def healthcheck(self) -> dict[str, Any]:
        return self.transport.healthcheck()

    def generate_final_report_text(
        self,
        *,
        competencies: dict[str, int],
        strengths: list[str],
        improvement_points: list[str],
        visual_context: dict[str, Any],
        audio_context: dict[str, Any],
        cv_profile: dict[str, Any],
        turns: list[dict[str, Any]],
        response_language: str = "fr",
    ) -> dict[str, Any]:
        return generate_report_payload(
            request_json=self._request_json,
            competencies=competencies,
            strengths=strengths,
            improvement_points=improvement_points,
            visual_context=visual_context,
            audio_context=audio_context,
            cv_profile=cv_profile,
            turns=turns,
            response_language=response_language,
        )

    def infer_competencies_from_interview(
        self,
        *,
        cv_profile: dict[str, Any],
        turns: list[dict[str, Any]],
        response_language: str = "fr",
    ) -> dict[str, int]:
        return infer_scores_payload(
            request_json=self._request_json,
            normalize_scores=self._normalize_competency_scores,
            cv_profile=cv_profile,
            turns=turns,
            response_language=response_language,
        )

    def score_interview_turn(
        self,
        *,
        cv_profile: dict[str, Any],
        recent_turns: list[dict[str, Any]],
        question: str,
        answer: str,
        question_phase: str,
        response_language: str = "fr",
    ) -> dict[str, Any]:
        return score_turn_payload(
            request_json=self._request_json,
            normalize_scores=self._normalize_competency_scores,
            cv_profile=cv_profile,
            recent_turns=recent_turns,
            question=question,
            answer=answer,
            question_phase=question_phase,
            response_language=response_language,
        )

    def generate_insights_advice(
        self,
        *,
        visual_context: dict[str, Any],
        audio_context: dict[str, Any],
        stress_context: dict[str, Any],
        response_language: str = "fr",
    ) -> dict[str, Any]:
        return generate_insights_advice_payload(
            request_json=self._request_json,
            visual_context=visual_context,
            audio_context=audio_context,
            stress_context=stress_context,
            response_language=response_language,
        )

    def generate(
        self,
        *,
        text: str,
        candidate_name: str,
        session_id: str,
        session_state: dict[str, Any],
    ) -> dict[str, Any]:
        total_start = time.perf_counter()
        cv_profile = session_state.get("cv_profile", {})
        recent_turns = session_state.get("recent_turns", [])
        cv_context = session_state.get("cv_context") or session_state.get("rag_context") or []
        last_index = int(session_state.get("last_question_index", 0))
        phase = str(session_state.get("phase", "QUESTION_1")).upper()
        if phase not in self.VALID_PHASES:
            phase = "QUESTION_1"
        stored_language = str(session_state.get("response_language", "") or "").strip().lower()
        lang = stored_language if stored_language in {"fr", "en"} else detect_response_language(text)

        if session_state.get("rephrase_only"):
            return self._build_rephrase_payload(
                session_id=session_id,
                candidate_name=candidate_name,
                phase=phase,
                lang=lang,
                text=text,
                question_to_rephrase=str(session_state.get("question_to_rephrase", "")).strip(),
                question_index=max(1, int(session_state.get("rephrase_question_index", last_index or 1))),
                cv_profile=cv_profile,
                cv_context=cv_context,
                recent_turns=recent_turns,
            )

        messages = build_generation_messages(
            session_id=session_id,
            candidate_name=candidate_name,
            phase=phase,
            lang=lang,
            text=text,
            recent_turns=recent_turns,
            cv_profile=cv_profile,
            rag_context=cv_context,
        )

        try:
            parsed = normalize_llm_payload(
                self._call_model(messages, phase=phase),
                phase,
                last_index,
            )

            if phase == "FINAL":
                parsed["say"] = ""
                return self._apply_turn_scoring(
                    parsed=parsed,
                    text=text,
                    phase=phase,
                    lang=lang,
                    cv_profile=cv_profile,
                    cv_context=cv_context,
                    recent_turns=recent_turns,
                )

            parsed = self._validate_or_repair_question(
                parsed=parsed,
                messages=messages,
                phase=phase,
                lang=lang,
                text=text,
                cv_profile=cv_profile,
                cv_context=cv_context,
                recent_turns=recent_turns,
                session_id=session_id,
                total_start=total_start,
                last_index=last_index,
            )
            return self._apply_turn_scoring(
                parsed=parsed,
                text=text,
                phase=phase,
                lang=lang,
                cv_profile=cv_profile,
                cv_context=cv_context,
                recent_turns=recent_turns,
            )
        except APIConnectionError as exc:
            logger.exception("Erreur lors de la generation", exc_info=exc)
            diag = self.healthcheck()
            server_error = diag.get("error", "erreur de connexion inconnue")
            provider_label = self.provider_name.title()
            raise RuntimeError(
                f"Serveur LLM indisponible via {provider_label} ({self.base_url}) ; modele configure: {self.model}. "
                f"Diagnostic: {server_error}. "
                "Verifiez que le service est accessible, que la cle API est valide et que le modele est disponible."
            ) from exc
        except LLMRateLimitError:
            raise
        except Exception as exc:
            logger.exception("Erreur lors de la generation", exc_info=exc)
            raise RuntimeError(
                f"Echec generation LLM via {self.provider_name} ({self.model}): {exc}"
            ) from exc

