import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any

from interview_ai.constants import RH_ALLOWED_MARKERS, RH_MOTIVATION_MARKERS, RH_TECH_MARKERS
from interview_ai.prompts import build_cv_anchor_terms, normalize_cv_profile


KNOWN_TECH_TERMS = (
    "spring boot",
    "react",
    "node.js",
    "node js",
    "mongodb",
    "mongo db",
    "java",
    "typescript",
    "javascript",
    "angular",
    "vue",
    "django",
    "flask",
    "fastapi",
    "postgresql",
    "mysql",
    "docker",
    "kubernetes",
)

BEHAVIOR_PROJECT_MARKERS = (
    "projet",
    "application",
    "plateforme",
    "experience",
    "stage",
    "mission",
    "chez ",
    "lors de",
)

BEHAVIOR_CHALLENGE_MARKERS = (
    "situation",
    "exemple",
    "defi",
    "difficulte",
    "probleme",
    "blocage",
    "desaccord",
    "challenge",
)

LOW_LEVEL_IMPLEMENTATION_MARKERS = (
    "composant",
    "component",
    "api ",
    " api",
    "endpoint",
    "controller",
    "controleur",
    "service",
    "repository",
    "base de donnees",
    "database",
    "hook",
    "fonction",
    "method",
    "methode",
)

OVERLY_AFFIRMATIVE_BEHAVIOR_PATTERNS = (
    r"\bune situation ou vous avez (?:du|deja du) ger",
    r"\bdecrire une situation ou vous avez (?:du|deja du) ger",
    r"\bdecrivez une situation ou vous avez (?:du|deja du) ger",
    r"\bracontez une situation ou vous avez (?:du|deja du) ger",
)

GENERIC_BEHAVIOR_PROJECT_PATTERNS = (
    r"\bsur l[' ]un de vos projets\b",
    r"\bdans l[' ]un de vos projets\b",
    r"\bon one of your projects\b",
    r"\bin one of your projects\b",
)

NON_INTRO_PREAMBLE_MARKERS = (
    "bonjour",
    "hello",
    "hi ",
    "ravi de vous rencontrer",
    "nice to meet you",
    "vous etes",
    "vous êtes",
    "you are",
)

QUESTION_START_RE = re.compile(
    r"\b("
    r"pouvez[-\u2010-\u2015\u2212]?vous|peux[-\u2010-\u2015\u2212]?tu|pouvez vous|parlez[-\u2010-\u2015\u2212]?moi|parlez moi|racontez[-\u2010-\u2015\u2212]?moi|racontez moi|"
    r"decrivez|decrivez-moi|decrivez moi|racontez|quelle|quel|quelles|quels|comment|"
    r"qu['’]est[-\u2010-\u2015\u2212]?ce|qu est ce|avez[-\u2010-\u2015\u2212]?vous|avez vous|dans quelle|could you|can you|tell me|"
    r"what|which|how|why"
    r")\b",
    flags=re.I,
)

INCOMPLETE_QUESTION_ENDINGS = (
    " de ?",
    " sur ?",
    " avec ?",
    " dans ?",
    " pour ?",
    " parlez de ?",
    " parler de ?",
)


def _normalize_matching_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", " ".join((text or "").split()).lower())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.replace("‑", "-").replace("–", "-").replace("—", "-")
    normalized = normalized.replace("’", "'").replace("`", "'")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _normalize_question_surface(text: str) -> str:
    normalized = " ".join((text or "").split()).strip()
    for char in ("‐", "‑", "‒", "–", "—", "―", "−"):
        normalized = normalized.replace(char, "-")
    for char in ("‘", "’", "′"):
        normalized = normalized.replace(char, "'")
    return normalized


def normalize_interviewer_question(question: str, phase: str) -> str:
    text = _normalize_question_surface(question)
    if not text:
        return ""
    text = re.sub(r'^\s*Dans la situation\s+["\'].*?["\']\s*,\s*', "Dans cette situation, ", text, flags=re.I)
    text = re.sub(r"^\s*Comment vous (?:gerer|gerez)\b", "Comment gerez-vous", text, flags=re.I)
    text = re.sub(r"^\s*Comment vous avez gere\b", "Comment avez-vous gere", text, flags=re.I)
    if phase == "MOTIVATION":
        text = re.sub(r"\bSUBUL\b", "notre entreprise", text, flags=re.I)
    lowered = _normalize_matching_text(text)
    if any(lowered.startswith(prefix) for prefix in ("je suis", "je m'appelle", "je peux", "je vais", "moi,", "en tant que")):
        return ""
    if phase != "INTRO":
        if any(marker in lowered for marker in NON_INTRO_PREAMBLE_MARKERS):
            matches = list(QUESTION_START_RE.finditer(text))
            if matches:
                match = matches[-1]
                if match.start() > 0:
                    text = text[match.start():].strip(" ,")
                    lowered = _normalize_matching_text(text)
        if "?" in text:
            segments = [segment.strip(" ,") for segment in re.split(r"(?<=[.!])\s+", text) if segment.strip(" ,")]
            question_segments = [segment for segment in segments if "?" in segment]
            if question_segments:
                text = question_segments[-1]
                lowered = _normalize_matching_text(text)
        if any(marker in lowered for marker in NON_INTRO_PREAMBLE_MARKERS):
            matches = list(QUESTION_START_RE.finditer(text))
            if matches:
                match = matches[-1]
                if match.start() > 0:
                    text = text[match.start():].strip(" ,")
                    lowered = _normalize_matching_text(text)
        if any(marker in lowered for marker in NON_INTRO_PREAMBLE_MARKERS):
            raise ValueError("Question LLM contient un preambule INTRO hors phase INTRO")
    if text.count("?") > 1:
        text = text.split("?", 1)[0].strip() + " ?"
    if "?" not in text:
        text = text.rstrip(".!;:,") + " ?"
    return text


def question_fingerprint(question: str) -> str:
    normalized = unicodedata.normalize("NFKD", " ".join((question or "").lower().split()))
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(
        r"\b(pouvez vous|peux tu|merci|bonjour|decrire|comment|avez vous|avez|vous|dans|cette|situation|quel|quelle|quels|quelles)\b",
        " ",
        normalized,
    )
    normalized = re.sub(
        r"\b(projet|application|plateforme|suivi client|stage|stagiaire|developpement web|projet de suivi client|dans ce projet|dans l un de vos projets)\b",
        " ",
        normalized,
    )
    normalized = re.sub(
        r"\b(frontend|backend|front end|back end|api|base de donnees|module|modules|interface|endpoints?)\b",
        " ",
        normalized,
    )
    return re.sub(r"\s+", " ", normalized).strip()


def question_token_set(question: str) -> set[str]:
    fingerprint = question_fingerprint(question)
    return {
        token
        for token in fingerprint.split()
        if len(token) > 3
        and token not in {"avez", "vous", "comment", "cette", "situation", "projet", "application"}
    }

def _flatten_context(cv_profile: dict[str, Any], rag_context: list[str], current_text: str) -> str:
    parts: list[str] = []
    if isinstance(cv_profile, dict):
        for key in ("headline", "text_preview"):
            value = str(cv_profile.get(key, "")).strip()
            if value:
                parts.append(value)
        for key in ("top_skills", "projects"):
            for item in cv_profile.get(key, [])[:8]:
                cleaned = str(item).strip()
                if cleaned:
                    parts.append(cleaned)
    for item in rag_context[:5]:
        cleaned = str(item).strip()
        if cleaned:
            parts.append(cleaned)
    if current_text:
        parts.append(current_text)
    return " ".join(parts).lower()


def has_unsupported_specific_tech(
    question: str,
    *,
    cv_profile: dict[str, Any],
    rag_context: list[str],
    current_text: str,
) -> bool:
    lowered = _normalize_matching_text(question)
    context_blob = _normalize_matching_text(_flatten_context(cv_profile, rag_context, current_text))
    for term in KNOWN_TECH_TERMS:
        normalized_term = _normalize_matching_text(term)
        if normalized_term in lowered and normalized_term not in context_blob:
            return True
    return False

def is_overly_narrow_behavior_question(question: str, target_phase: str, recent_turns: list[dict[str, Any]]) -> bool:
    if target_phase != "BEHAVIOR" or len(recent_turns) > 1:
        return False

    lowered = f" {_normalize_matching_text(question)} "
    has_project_anchor = any(marker in lowered for marker in BEHAVIOR_PROJECT_MARKERS)
    has_challenge_angle = any(marker in lowered for marker in BEHAVIOR_CHALLENGE_MARKERS)
    has_low_level_marker = any(marker in lowered for marker in LOW_LEVEL_IMPLEMENTATION_MARKERS)
    return has_low_level_marker and (not has_project_anchor or not has_challenge_angle)


def is_overly_affirmative_behavior_question(question: str, target_phase: str, recent_turns: list[dict[str, Any]]) -> bool:
    if target_phase != "BEHAVIOR" or len(recent_turns) > 1:
        return False

    lowered = _normalize_matching_text(question)
    return any(re.search(pattern, lowered) for pattern in OVERLY_AFFIRMATIVE_BEHAVIOR_PATTERNS)


def _candidate_anchor_variants(cv_profile: dict[str, Any], rag_context: list[str]) -> list[str]:
    profile = normalize_cv_profile(cv_profile)
    variants: list[str] = []
    seen: set[str] = set()

    def add_variant(value: str) -> None:
        normalized = _normalize_matching_text(value)
        if not normalized or len(normalized) < 4 or normalized in seen:
            return
        seen.add(normalized)
        variants.append(normalized)

    for project in profile.get("projects", [])[:4]:
        add_variant(str(project))

    for anchor in build_cv_anchor_terms(profile, rag_context)[:6]:
        add_variant(anchor)

    headline = str(profile.get("headline", "")).strip()
    if headline:
        add_variant(headline)

    return variants


def has_generic_behavior_project_reference(
    question: str,
    *,
    target_phase: str,
    recent_turns: list[dict[str, Any]],
    cv_profile: dict[str, Any],
    rag_context: list[str],
) -> bool:
    if target_phase != "BEHAVIOR" or len(recent_turns) > 1:
        return False

    lowered = _normalize_matching_text(question)
    if not any(re.search(pattern, lowered) for pattern in GENERIC_BEHAVIOR_PROJECT_PATTERNS):
        return False

    anchors = _candidate_anchor_variants(cv_profile, rag_context)
    if not anchors:
        return False

    return True

def validate_candidate_question(
    *,
    question: str,
    target_phase: str,
    recent_turns: list[dict[str, Any]],
    cv_profile: dict[str, Any] | None = None,
    rag_context: list[str] | None = None,
    current_text: str = "",
) -> str:
    normalized = normalize_interviewer_question(question, target_phase)
    if not normalized:
        raise ValueError("Question LLM invalide ou vide")
    lowered = _normalize_matching_text(normalized)
    token_count = len([token for token in lowered.replace("?", " ").split() if token])
    if token_count < 5 or any(lowered.endswith(ending.strip()) for ending in INCOMPLETE_QUESTION_ENDINGS):
        raise ValueError("Question LLM incomplete")
    if is_overly_narrow_behavior_question(normalized, target_phase, recent_turns):
        raise ValueError("Question LLM BEHAVIOR trop detaillee")
    if is_overly_affirmative_behavior_question(normalized, target_phase, recent_turns):
        raise ValueError("Question LLM BEHAVIOR trop affirmative")
    if has_generic_behavior_project_reference(
        normalized,
        target_phase=target_phase,
        recent_turns=recent_turns,
        cv_profile=cv_profile or {},
        rag_context=rag_context or [],
    ):
        raise ValueError("Question LLM BEHAVIOR trop generique")
    if has_unsupported_specific_tech(
        normalized,
        cv_profile=cv_profile or {},
        rag_context=rag_context or [],
        current_text=current_text,
    ):
        raise ValueError("Question LLM hors contexte CV")
    return normalized
