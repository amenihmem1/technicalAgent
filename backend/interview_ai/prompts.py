from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, is_dataclass
from difflib import SequenceMatcher
from typing import Any

from interview_ai.constants import (
    ENGLISH_MARKERS,
    FRENCH_MARKERS,
    GENERIC_PROJECT_FILTER,
    MAX_ANCHOR_LENGTH,
    MAX_CONTEXT_SNIPPET,
    MAX_LAST_ANSWER_FOCUS,
    MAX_PREVIEW_LENGTH,
)

_GENERIC_RAG_MARKERS = {
    "cours",
    "chapter",
    "chapitre",
    "introduction",
    "resume",
    "summary",
    "concept",
    "concepts",
    "definition",
    "definitions",
    "module",
}
_TECH_KEYWORDS = {
    "api",
    "architecture",
    "backend",
    "bug",
    "ci/cd",
    "cloud",
    "css",
    "data",
    "database",
    "debug",
    "deployment",
    "devops",
    "django",
    "docker",
    "fastapi",
    "frontend",
    "git",
    "java",
    "javascript",
    "kubernetes",
    "langchain",
    "llm",
    "microservice",
    "mongodb",
    "mysql",
    "node",
    "performance",
    "postgresql",
    "python",
    "react",
    "rest",
    "scalability",
    "security",
    "spring",
    "sql",
    "testing",
    "typescript",
    "websocket",
}
_CLAUSE_SPLIT_RE = re.compile(r"(?<=[\.\!\?\;\:])\s+")


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _to_folded_text(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.replace("'", " ")
    return " ".join(normalized.lower().split()).strip()


def _truncate(value: Any, limit: int) -> str:
    cleaned = _clean_text(value)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip(" ,;:.") + "..."


def _coerce_string_list(values: Any, *, limit: int | None = None) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []
    items: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean_text(value)
        if not cleaned:
            continue
        key = _to_folded_text(cleaned)
        if key in seen:
            continue
        seen.add(key)
        items.append(cleaned)
        if limit is not None and len(items) >= limit:
            break
    return items


def _normalize_profile_source(profile: Any) -> dict[str, Any]:
    if is_dataclass(profile):
        try:
            return asdict(profile)
        except Exception:
            return dict(getattr(profile, "__dict__", {}) or {})
    if isinstance(profile, dict):
        return dict(profile)
    if hasattr(profile, "__dict__"):
        return dict(getattr(profile, "__dict__", {}) or {})
    return {}


def normalize_cv_profile(profile: Any) -> dict[str, Any]:
    raw = _normalize_profile_source(profile)

    candidate_name = (
        _clean_text(raw.get("candidate_name"))
        or _clean_text(raw.get("name"))
    )
    headline = _clean_text(raw.get("headline"))
    email = _clean_text(raw.get("email"))
    phone = _clean_text(raw.get("phone"))
    linkedin = _clean_text(raw.get("linkedin"))
    github = _clean_text(raw.get("github"))
    source_filename = _clean_text(raw.get("source_filename"))
    text_preview = _truncate(raw.get("text_preview", ""), MAX_PREVIEW_LENGTH)

    try:
        overall_confidence = float(raw.get("overall_confidence", 0.0) or 0.0)
    except Exception:
        overall_confidence = 0.0

    normalized = {
        "candidate_name": candidate_name,
        "name": candidate_name,
        "headline": headline,
        "email": email,
        "phone": phone,
        "linkedin": linkedin,
        "github": github,
        "top_skills": _coerce_string_list(raw.get("top_skills"), limit=10),
        "experiences": _coerce_string_list(raw.get("experiences"), limit=8),
        "projects": _coerce_string_list(raw.get("projects"), limit=8),
        "confidence": raw.get("confidence") if isinstance(raw.get("confidence"), dict) else {},
        "overall_confidence": overall_confidence,
        "text_preview": text_preview,
        "source_filename": source_filename,
    }
    return normalized


def _format_anchor(value: Any) -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        return ""
    cleaned = re.sub(r"^[\-\*\u2022]+\s*", "", cleaned)
    cleaned = cleaned.strip(" ,;:.|-")
    if not cleaned:
        return ""
    if len(cleaned) > MAX_ANCHOR_LENGTH:
        cleaned = cleaned[:MAX_ANCHOR_LENGTH].rstrip(" ,;:.") + "..."
    return cleaned


def _is_generic_anchor(text: str) -> bool:
    lowered = _to_folded_text(text)
    if not lowered:
        return True
    if lowered in GENERIC_PROJECT_FILTER:
        return True
    if len(lowered) < 3:
        return True
    if lowered in _GENERIC_RAG_MARKERS:
        return True
    if lowered.startswith("page ") or lowered.startswith("section "):
        return True
    return False


def _extract_rag_anchor(chunk: str) -> str:
    cleaned = _clean_text(chunk)
    if not cleaned:
        return ""
    segments = [segment.strip(" -|,;:.") for segment in _CLAUSE_SPLIT_RE.split(cleaned) if segment.strip(" -|,;:.")]
    if not segments:
        segments = [cleaned]
    best = ""
    best_score = float("-inf")
    for segment in segments[:4]:
        candidate = _format_anchor(segment)
        lowered = _to_folded_text(candidate)
        if _is_generic_anchor(candidate):
            continue
        score = 0.0
        score += min(len(candidate), 90) / 90.0
        score += 1.2 if any(keyword in lowered for keyword in _TECH_KEYWORDS) else 0.0
        if ":" in segment:
            score += 0.2
        if score > best_score:
            best = candidate
            best_score = score
    return best or _format_anchor(cleaned[:MAX_CONTEXT_SNIPPET])


def build_cv_anchor_terms(profile: Any, rag_context: list[str] | None = None) -> list[str]:
    normalized = normalize_cv_profile(profile)
    anchors: list[str] = []
    seen: set[str] = set()

    def add_anchor(value: Any) -> None:
        candidate = _format_anchor(value)
        if not candidate or _is_generic_anchor(candidate):
            return
        key = _to_folded_text(candidate)
        if key in seen:
            return
        seen.add(key)
        anchors.append(candidate)

    headline = normalized.get("headline", "")
    if headline:
        add_anchor(headline)

    for skill in normalized.get("top_skills", [])[:8]:
        add_anchor(skill)

    for project in normalized.get("projects", [])[:6]:
        add_anchor(project)

    for experience in normalized.get("experiences", [])[:4]:
        add_anchor(experience)

    for chunk in list(rag_context or [])[:6]:
        add_anchor(_extract_rag_anchor(chunk))

    return anchors[:12]


def build_cv_summary(profile: Any) -> str:
    normalized = normalize_cv_profile(profile)
    parts: list[str] = []

    candidate_name = normalized.get("candidate_name", "")
    headline = normalized.get("headline", "")
    if candidate_name and headline:
        parts.append(f"{candidate_name} - {headline}")
    elif headline:
        parts.append(f"Profil cible: {headline}")
    elif candidate_name:
        parts.append(f"Candidat: {candidate_name}")

    top_skills = normalized.get("top_skills", [])
    if top_skills:
        parts.append(f"Competences: {', '.join(top_skills[:6])}")

    projects = normalized.get("projects", [])
    if projects:
        parts.append(f"Projets: {' | '.join(_truncate(item, 110) for item in projects[:2])}")

    experiences = normalized.get("experiences", [])
    if experiences:
        parts.append(f"Experiences: {' | '.join(_truncate(item, 110) for item in experiences[:2])}")

    if not parts and normalized.get("text_preview"):
        parts.append(f"Extrait CV: {_truncate(normalized['text_preview'], MAX_PREVIEW_LENGTH)}")

    return " ; ".join(part for part in parts if part).strip() or "Profil CV non disponible."


def extract_relevant_phrase(text: str) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return ""

    candidates = [segment.strip(" -|,;:.") for segment in _CLAUSE_SPLIT_RE.split(cleaned) if segment.strip(" -|,;:.")]
    if not candidates:
        candidates = [cleaned]

    best = ""
    best_score = float("-inf")
    for segment in candidates[:5]:
        lowered = _to_folded_text(segment)
        score = 0.0
        score += min(len(segment), MAX_LAST_ANSWER_FOCUS) / MAX_LAST_ANSWER_FOCUS
        score += 1.5 if any(keyword in lowered for keyword in _TECH_KEYWORDS) else 0.0
        score += 0.4 if any(char.isdigit() for char in segment) else 0.0
        score += 0.2 if "," in segment or ":" in segment else 0.0
        if score > best_score:
            best = segment
            best_score = score
    return _truncate(best or cleaned, MAX_LAST_ANSWER_FOCUS)


def _anchor_score(
    anchor: str,
    *,
    current_text: str,
    recent_turns: list[dict[str, Any]] | None,
    rag_context: list[str] | None,
) -> float:
    lowered_anchor = _to_folded_text(anchor)
    if not lowered_anchor:
        return float("-inf")

    score = 0.0
    current_folded = _to_folded_text(current_text)
    if current_folded:
        if lowered_anchor in current_folded:
            score += 3.5
        score += SequenceMatcher(None, lowered_anchor, current_folded).ratio()

    for weight, turn in enumerate(reversed(list(recent_turns or [])[-3:]), start=1):
        if not isinstance(turn, dict):
            continue
        answer_text = _to_folded_text(turn.get("candidate_text", ""))
        question_text = _to_folded_text(turn.get("say", ""))
        if lowered_anchor and lowered_anchor in answer_text:
            score += 1.4 / weight
        if lowered_anchor and lowered_anchor in question_text:
            score += 0.8 / weight

    for index, chunk in enumerate(list(rag_context or [])[:4], start=1):
        chunk_folded = _to_folded_text(chunk)
        if lowered_anchor and lowered_anchor in chunk_folded:
            score += 1.0 / index

    if any(keyword == lowered_anchor for keyword in _TECH_KEYWORDS):
        score += 0.6
    if len(anchor.split()) >= 3:
        score += 0.25
    return score


def select_behavior_anchor(
    profile: Any,
    *,
    rag_context: list[str] | None = None,
    recent_turns: list[dict[str, Any]] | None = None,
    current_text: str = "",
    session_id: str = "",
) -> str:
    del session_id
    anchors = build_cv_anchor_terms(profile, rag_context)
    if not anchors:
        return ""

    ranked = sorted(
        anchors,
        key=lambda anchor: _anchor_score(
            anchor,
            current_text=current_text,
            recent_turns=recent_turns,
            rag_context=rag_context,
        ),
        reverse=True,
    )
    return ranked[0] if ranked else ""


def detect_response_language(text: str) -> str:
    lowered = f" {_to_folded_text(text)} "
    if not lowered.strip():
        return "fr"

    fr_hits = sum(1 for marker in FRENCH_MARKERS if marker in lowered)
    en_hits = sum(1 for marker in ENGLISH_MARKERS if marker in lowered)

    if en_hits > fr_hits:
        return "en"
    if fr_hits > en_hits:
        return "fr"

    english_hint_words = (
        " the ",
        " and ",
        " with ",
        " my ",
        " i ",
        " we ",
        " team ",
        " project ",
        " what ",
        " why ",
        " how ",
        " can you ",
        " could you ",
        " does ",
        " do ",
    )
    if any(marker in lowered for marker in english_hint_words):
        return "en"
    return "fr"


def build_chat_messages(*, system_content: str, user_content: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _clean_text(system_content)},
        {"role": "user", "content": _clean_text(user_content)},
    ]


def _history_lines(recent_turns: list[dict[str, Any]] | None) -> list[str]:
    lines: list[str] = []
    for turn in list(recent_turns or [])[-4:]:
        if not isinstance(turn, dict):
            continue
        question = _truncate(turn.get("say", ""), 180)
        answer = _truncate(turn.get("candidate_text", ""), 220)
        phase = _clean_text(turn.get("phase", ""))
        if question or answer:
            lines.append(f"- {phase or 'TURN'} | Q: {question or '[vide]'} | R: {answer or '[vide]'}")
    return lines


def _rag_lines(rag_context: list[str] | None) -> list[str]:
    return [f"- {_truncate(chunk, MAX_CONTEXT_SNIPPET)}" for chunk in list(rag_context or [])[:4] if _clean_text(chunk)]


def _get_skill_for_phase(phase: str) -> str:
    del phase
    return "question_score"


def _json_shape_hint(target_phase: str, question_index: int) -> str:
    say_value = "" if target_phase == "FINAL" else "Question technique concrete basee sur le CV"
    target_skill = _get_skill_for_phase(target_phase)
    
    # For FINAL phase, no new answer is graded.
    if target_phase == "FINAL":
        return (
            "{"
            f'"phase":"{target_phase}",'
            f'"question_index":{question_index},'
            f'"say":"{say_value}",'
            '"score_partial":{"question_score":0},'
            '"notes":[],"final_report":null'
            "}"
        )
    
    del target_skill
    
    return (
        "{"
        f'"phase":"{target_phase}",'
        f'"question_index":{question_index},'
        f'"say":"{say_value}",'
        '"score_partial":{"question_score":0},'
        '"notes":[],"final_report":null'
        "}"
    )


def _resolve_question_index(
    phase: str,
    recent_turns: list[dict[str, Any]] | None,
) -> int:
    if str(phase or "").upper() == "FINAL":
        for turn in reversed(list(recent_turns or [])):
            if not isinstance(turn, dict):
                continue
            try:
                return max(1, int(turn.get("question_index", 1)))
            except Exception:
                continue
        return 1

    for turn in reversed(list(recent_turns or [])):
        if not isinstance(turn, dict):
            continue
        try:
            return max(1, int(turn.get("question_index", 0)) + 1)
        except Exception:
            continue
    return 1


def _extract_course_themes(rag_context: list[str] | None) -> dict[str, str]:
    """Extract main themes/topics from course material to adapt questions."""
    if not rag_context or len(rag_context) == 0:
        return {
            "theme": "general",
            "context": "",
            "focus": "technical content",
        }
    
    # Combine course snippets
    course_text = " ".join(str(chunk or "") for chunk in rag_context[:5])
    course_text_lower = _to_folded_text(course_text)
    
    # Detect course theme/domain
    theme_keywords = {
        "machine learning": ["machine", "learning", "neural", "model", "training", "algorithm", "ai"],
        "web development": ["web", "frontend", "backend", "http", "api", "react", "django", "flask"],
        "data engineering": ["data", "etl", "pipeline", "warehouse", "spark", "hadoop", "database"],
        "cloud": ["cloud", "aws", "azure", "gcp", "docker", "kubernetes", "infrastructure"],
        "security": ["security", "encryption", "auth", "ssl", "vulnerability", "exploit"],
        "performance": ["performance", "optimization", "cache", "latency", "throughput", "scalability"],
    }
    
    theme = "general"
    max_matches = 0
    for candidate_theme, keywords in theme_keywords.items():
        matches = sum(1 for kw in keywords if kw in course_text_lower)
        if matches > max_matches:
            max_matches = matches
            theme = candidate_theme
    
    context_snippet = _truncate(course_text, 300)
    
    return {
        "theme": theme,
        "context": context_snippet,
        "focus": theme.replace("_", " ").title(),
    }


def _adaptive_phase_goal(phase: str, course_theme: str, lang: str) -> str:
    """Generate phase goals adapted to the specific course theme."""
    if lang == "en":
        base_goals = {
            "QUESTION_1": f"Start with a fundamental technical question connected to the candidate CV and {course_theme}",
            "QUESTION_2": f"Ask about an application or example tied to the candidate CV, projects, skills, or {course_theme} course material",
            "QUESTION_3": f"Examine a challenge, limit, property, or trade-off related to a CV technology/project or {course_theme}",
            "QUESTION_4": f"Synthesize and assess the candidate's understanding through a technical scenario grounded in the CV or {course_theme}",
            "FINAL": "close the interview without asking a new question",
        }
    else:
        base_goals = {
            "QUESTION_1": f"Démarrer avec une question fondamentale sur les concepts de {course_theme} du cours",
            "QUESTION_2": f"Demander comment appliquer les concepts de {course_theme} dans un scénario pratique",
            "QUESTION_3": f"Examiner un défi ou compromis spécifique de {course_theme} du cours",
            "QUESTION_4": f"Synthétiser et évaluer la compréhension du candidat sur {course_theme}",
            "FINAL": "clore l'entretien sans poser de nouvelle question",
        }
    if lang != "en":
        base_goals.update(
            {
                "QUESTION_1": f"Demander une notion technique fondamentale visible dans le CV ou le materiel {course_theme}",
                "QUESTION_2": f"Demander une application ou un exemple a partir d'un projet/skill du CV ou du materiel {course_theme}",
                "QUESTION_3": f"Demander une limite, propriete, comparaison ou compromis lie au CV ou au materiel {course_theme}",
                "QUESTION_4": f"Poser une question de synthese a partir du CV candidat ou du materiel {course_theme}",
            }
        )

    return base_goals.get(str(phase or "").upper(), base_goals["QUESTION_2"])


def build_generation_messages(
    *,
    session_id: str,
    candidate_name: str,
    phase: str,
    lang: str,
    text: str,
    recent_turns: list[dict[str, Any]] | None,
    cv_profile: Any,
    rag_context: list[str] | None,
) -> list[dict[str, str]]:
    normalized = normalize_cv_profile(cv_profile)
    resolved_phase = str(phase or "QUESTION_1").upper()
    question_index = _resolve_question_index(resolved_phase, recent_turns)
    
    # Extract course theme to adapt questions
    course_info = _extract_course_themes(rag_context)
    course_theme = course_info["theme"]
    
    cv_summary = build_cv_summary(normalized)
    anchors = build_cv_anchor_terms(normalized, rag_context)[:6]
    focus_phrase = extract_relevant_phrase(text)
    best_anchor = select_behavior_anchor(
        normalized,
        rag_context=rag_context,
        recent_turns=recent_turns,
        current_text=text,
        session_id=session_id,
    )
    history_block = "\n".join(_history_lines(recent_turns)) or "- Aucun historique exploitable"
    rag_block = "\n".join(_rag_lines(rag_context)) or "- Aucun passage RAG pertinent"
    anchors_block = ", ".join(anchors) if anchors else "Aucune ancre fiable"
    resolved_name = _clean_text(candidate_name) or normalized.get("candidate_name") or "Candidate"
    is_cv_question = resolved_phase == "QUESTION_1"
    phase_override = (
        (
            "OVERRIDE PHASE RULES:\n"
            f"- Current phase is {resolved_phase}.\n"
            "- QUESTION_1: greet the candidate by name, then ask exactly one technical question about the candidate CV.\n"
            "- QUESTION_2, QUESTION_3, QUESTION_4: ask exactly one technical question strictly about the course material, not the CV.\n"
        )
        if lang == "en"
        else (
            "REGLES PRIORITAIRES PAR PHASE:\n"
            f"- Phase courante: {resolved_phase}.\n"
            "- QUESTION_1: commence par Bonjour + nom du candidat, puis pose exactement une question technique sur le CV du candidat.\n"
            "- QUESTION_2, QUESTION_3, QUESTION_4: pose exactement une question technique strictement sur le cours, pas sur le CV.\n"
        )
    )

    if is_cv_question:
        cv_grounding_rules = (
            f"Resume CV:\n{cv_summary}\n\n"
            f"Ancres CV: {anchors_block}\n"
            "Regles question CV:\n"
            "- Pose une seule question technique ancree dans le CV candidat.\n"
            "- Privilegie une competence, un projet ou une experience du CV quand une ancre fiable est disponible.\n"
            "- Commence par Bonjour/Hello + nom du candidat.\n"
            "- Ne pose pas de question RH, de motivation ou personnelle non technique.\n\n"
        )
    else:
        cv_grounding_rules = (
            "Regles question cours uniquement:\n"
            "- Pose une seule question technique strictement ancree dans le materiel de cours fourni.\n"
            "- N'utilise pas le CV, les projets, l'experience ou les competences du candidat pour cette phase.\n"
            "- Choisis une notion, methode, definition, mecanisme, comparaison, limite ou exemple visible dans le cours.\n\n"
        )

    if lang == "en":
        system = (
            "You are a technical examiner conducting a structured oral examination. "
            "You must write every interviewer question in English. "
            "Your job is to ask exactly one natural technical question per turn. "
            "QUESTION_1 must be grounded in the candidate CV. QUESTION_2, QUESTION_3, and QUESTION_4 must be grounded strictly in the course material. "
            "Evaluate how well the candidate understands and can apply the technical concepts. "
            "Score the answer fairly on a 0-5 scale. Reply ONLY with valid JSON."
        )
        user = phase_override + "\n" + cv_grounding_rules + (
            f"Session: {session_id or 'n/a'}\n"
            f"Candidate: {resolved_name}\n"
            f"Target phase: {resolved_phase}\n"
            f"Course focus: {course_theme}\n"
            f"Goal: {_adaptive_phase_goal(resolved_phase, course_theme, lang)}\n"
            f"Candidate latest answer: {_truncate(text, 500) or '[empty]'}\n"
            f"CV summary:\n{cv_summary}\n\n"
            f"CV anchors: {anchors_block}\n"
            f"Course material:\n{rag_block}\n\n"
            f"Recent turns:\n{history_block}\n\n"
            "Rules:\n"
            "- Ask exactly one technical question if the phase starts with QUESTION_.\n"
            f"- For this current phase: {'ask about the CV and include a greeting with the candidate name' if is_cv_question else 'ask strictly about the course material and do not mention the CV'}.\n"
            "- Keep the question clear and fair for an examination.\n"
            "- Ask the question directly; do not cite file names, PDF names, or retrieval techniques.\n"
            "- Do not ask motivation, HR, or non-technical personal questions.\n"
            "- If both CV and course context are empty, do not invent a technical topic; ask for the CV/context to be uploaded.\n"
            "- Avoid repeating previous questions.\n"
            "- Do not mention that you are using course material or retrieval techniques.\n"
            "- Score the candidate's answer 0-5 based on correctness and understanding.\n"
            "- The score_partial.question_score must grade the candidate's latest answer like an exam answer.\n"
            f"- Return ONLY this JSON shape:\n{_json_shape_hint(resolved_phase, question_index)}"
        )
    else:
        system = (
            "Tu dois ecrire toutes les questions de l'interviewer en francais. "
            "Tu es un examinateur technique conduisant un examen oral structuré. "
            "Tu dois poser exactement une question technique naturelle par tour. "
            "QUESTION_1 doit etre basee sur le CV candidat. QUESTION_2, QUESTION_3 et QUESTION_4 doivent etre strictement basees sur le contenu du cours fourni. "
            "Les questions doivent être STRICTEMENT basées sur le contenu du cours, jamais inventées. "
            "Évalue comment le candidat comprend et peut appliquer les concepts du cours. "
            "Note la réponse équitablement sur une échelle 0-5. Réponds UNIQUEMENT avec un JSON valide."
        )
        user = phase_override + "\n" + cv_grounding_rules + (
            f"Session: {session_id or 'n/a'}\n"
            f"Candidat: {resolved_name}\n"
            f"Phase cible: {resolved_phase}\n"
            f"Focus du cours: {course_theme}\n"
            f"Objectif: {_adaptive_phase_goal(resolved_phase, course_theme, lang)}\n"
            f"Dernière réponse candidat: {_truncate(text, 500) or '[vide]'}\n"
            f"Matériel de cours:\n{rag_block}\n\n"
            f"Historique récent:\n{history_block}\n\n"
            "Règles:\n"
            f"- Pour cette phase: {'pose une question sur le CV et commence par Bonjour + nom du candidat' if is_cv_question else 'pose une question strictement sur le contenu du cours et ne mentionne pas le CV'}.\n"
            "- Garde la question claire et équitable pour un examen.\n"
            "- Pose la question directement; ne cite pas le titre du chapitre, le nom du fichier, le PDF, ni 'selon le cours'.\n"
            "- Si le materiel de cours est vide ou qu'aucun passage pertinent n'est disponible, n'invente pas de question technique; dis que le cours n'est pas disponible.\n"
            "- Évite les répétitions de questions précédentes.\n"
            "- Ne mentionne jamais que tu utilises du matériel de cours ou des techniques de récupération.\n"
            "- Note la réponse du candidat 0-5 basé sur la justesse et la compréhension.\n"
            "- Fournis une justification (evidence) pour ta note.\n"
            f"- Retourne UNIQUEMENT ce JSON:\n{_json_shape_hint(resolved_phase, question_index)}"
        )
    return build_chat_messages(system_content=system, user_content=user)


def build_rephrase_messages(
    *,
    session_id: str,
    candidate_name: str,
    phase: str,
    lang: str,
    clarification_text: str,
    original_question: str,
    question_index: int,
    recent_turns: list[dict[str, Any]] | None,
    cv_profile: Any,
    rag_context: list[str] | None,
) -> list[dict[str, str]]:
    normalized = normalize_cv_profile(cv_profile)
    cv_summary = build_cv_summary(normalized)
    anchors = build_cv_anchor_terms(normalized, rag_context)[:5]
    history_block = "\n".join(_history_lines(recent_turns)) or "- Aucun historique exploitable"
    rag_block = "\n".join(_rag_lines(rag_context)) or "- Aucun passage RAG pertinent"
    resolved_name = _clean_text(candidate_name) or normalized.get("candidate_name") or "Candidate"

    if lang == "en":
        system = (
            "You are a technical interviewer rephrasing your own question. "
            "Rewrite the original question more simply without changing its technical intent. "
            "Do not add a new topic. Reply ONLY with valid JSON."
        )
        user = (
            f"Session: {session_id or 'n/a'}\n"
            f"Candidate: {resolved_name}\n"
            f"Phase: {phase}\n"
            f"Candidate clarification request: {_truncate(clarification_text, 220) or '[empty]'}\n"
            f"Original question to rephrase: {original_question}\n"
            f"Anchor candidates: {', '.join(anchors) if anchors else 'n/a'}\n\n"
            f"CV summary:\n{cv_summary}\n\n"
            f"Retrieved context:\n{rag_block}\n\n"
            f"Recent turns:\n{history_block}\n\n"
            "Rules:\n"
            "- Keep the same technical goal.\n"
            "- Use simpler wording.\n"
            "- Ask one question only.\n"
            "- Do not add new technologies or examples not present in context.\n"
            f"- Return ONLY this JSON shape:\n{_json_shape_hint(str(phase).upper(), question_index)}"
        )
    else:
        system = (
            "Tu es un interviewer technique qui reformule sa propre question. "
            "Reecris la question initiale de facon plus simple sans changer son intention technique. "
            "N'ajoute pas un nouveau sujet. Reponds UNIQUEMENT avec un JSON valide."
        )
        user = (
            f"Session: {session_id or 'n/a'}\n"
            f"Candidat: {resolved_name}\n"
            f"Phase: {phase}\n"
            f"Demande de clarification: {_truncate(clarification_text, 220) or '[vide]'}\n"
            f"Question initiale a reformuler: {original_question}\n"
            f"Ancres candidates: {', '.join(anchors) if anchors else 'n/a'}\n\n"
            f"Resume CV:\n{cv_summary}\n\n"
            f"Contexte RAG:\n{rag_block}\n\n"
            f"Historique recent:\n{history_block}\n\n"
            "Regles:\n"
            "- Garde exactement le meme objectif technique.\n"
            "- Utilise des mots plus simples.\n"
            "- Pose une seule question.\n"
            "- N'ajoute aucune technologie ni exemple hors contexte.\n"
            f"- Retourne UNIQUEMENT ce JSON:\n{_json_shape_hint(str(phase).upper(), question_index)}"
        )
    return build_chat_messages(system_content=system, user_content=user)


def build_repair_instruction(reason: str) -> tuple[str, float]:
    lowered = _to_folded_text(reason)
    if "repet" in lowered:
        return (
            "Change clairement d'angle et pose une question differente mais toujours ancree dans le CV ou le contexte RAG.",
            0.45,
        )
    if "courte" in lowered or "incomplete" in lowered:
        return (
            "Regenere une question complete, concise, precise et techniquement exploitable.",
            0.35,
        )
    if "hors contexte" in lowered:
        return (
            "Repars strictement du CV, des passages recuperes et de la derniere reponse. N'invente rien.",
            0.2,
        )
    if "vide" in lowered or "invalide" in lowered:
        return (
            "Regenere un JSON valide avec une seule question technique naturelle.",
            0.3,
        )
    return (
        "Regenere une question technique plus naturelle, plus claire et mieux ancree dans le contexte fourni.",
        0.3,
    )
