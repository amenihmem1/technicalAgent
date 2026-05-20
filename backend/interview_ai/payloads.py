import json
import logging
import re
from typing import Any, Literal

from interview_ai.constants import SKILL_KEYS

# Configuration / Constantes (a synchroniser avec constants si besoin)
logger = logging.getLogger(__name__)

VALID_PHASES = {"QUESTION_1", "QUESTION_2", "QUESTION_3", "QUESTION_4", "FINAL"}

MAX_EVIDENCE_CHARS = 80       # évidence ultra-courte (1–4 mots idéalement)
MAX_NOTES = 2                 # max 2 notes très courtes

SKILL_ORDER = tuple(SKILL_KEYS)

# Parsing initial – très défensif contre les réponses LLM polluées
def parse_json_response(content: Any) -> dict[str, Any]:
    """
    Extrait un objet JSON valide même si le LLM a ajouté :
    - markdown ```json
    - préfixes texte ("Voici le JSON :", "Output :")
    - balises <think> ou réflexions
    - JSON tronqué / mal fermé
    """
    if isinstance(content, dict):
        return content

    raw = str(content or "").strip()
    if not raw:
        return {}

    # Nettoyage agressif
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.I | re.S)           # retire réflexions
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.M)     # retire blocs markdown
    raw = re.sub(
        r"^(?:Voici|Here is|Réponse|JSON|Output|Je retourne|Voici le JSON|Résultat).*?(\{.*)",
        r"\1", raw, flags=re.I | re.DOTALL | re.M
    )

    repaired = _try_parse_json_like_object(raw)
    if repaired:
        return repaired

    # Recherche du premier { et du } correspondant (compte les niveaux)
    start = raw.find("{")
    if start == -1:
        logger.warning("Aucun { trouvé → pas de JSON détecté", extra={"raw_preview": raw[:400]})
        return {}

    depth = 0
    end = -1
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if end == -1:
        truncated = raw[start:]
        balanced = _balance_brackets(truncated)
        try:
            parsed = json.loads(balanced)
            if isinstance(parsed, dict):
                logger.info("JSON tronqué réparé par fermeture automatique")
                return parsed
        except Exception:
            pass

        recovered = _recover_interview_payload(truncated)
        if recovered:
            logger.info("JSON tronqué récupéré via extraction défensive")
            return recovered

        logger.warning("JSON non fermé (tronqué)", extra={"raw_preview": truncated[:400]})
        return {}

    candidate = raw[start:end]

    # Tentatives de parsing (avec et sans virgules traînantes)
    for json_str in (
        candidate,
        re.sub(r",\s*([}\]])", r"\1", candidate),
        _repair_common_json_glitches(candidate),
    ):
        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError as e:
            logger.debug("Échec json.loads sur candidate", extra={"error": str(e), "snippet": json_str[:200]})

    recovered = _recover_interview_payload(candidate)
    if recovered:
        logger.info("JSON partiellement invalide récupéré via extraction défensive")
        return recovered

    logger.warning("Échec total de parsing JSON", extra={"raw_preview": raw[:400]})
    return {}


def _repair_common_json_glitches(text: str) -> str:
    repaired = str(text or "").strip()
    if not repaired:
        return repaired

    # trailing commas before closing braces/brackets
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
    # accidental empty quoted key fragment before object close: ... ," }
    repaired = re.sub(r',\s*"\s*([}\]])', r"\1", repaired)
    # common LLM corruption in nested dicts: {"a": {...},{"b": ...}}
    repaired = re.sub(r'(\{"level"\s*:\s*\d+\s*,\s*"evidence"\s*:\s*"[^"]*")\s*,\s*(?="\w+"\s*:)', r"\1}", repaired)
    repaired = re.sub(r'(\{"level"\s*:\s*\d+\s*,\s*"evidence"\s*:\s*"[^"]*")\s*(?=,\s*"\w+"\s*:)', r"\1}", repaired)
    return repaired


def _try_parse_json_like_object(text: str) -> dict[str, Any]:
    candidate = _repair_common_json_glitches(text)
    for json_str in (candidate, _balance_brackets(candidate)):
        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return {}


def _balance_brackets(text: str) -> str:
    balanced = str(text or "")
    if not balanced:
        return balanced

    open_curly = balanced.count("{")
    close_curly = balanced.count("}")
    open_square = balanced.count("[")
    close_square = balanced.count("]")
    if close_square < open_square:
        balanced += "]" * (open_square - close_square)
    if close_curly < open_curly:
        balanced += "}" * (open_curly - close_curly)
    return balanced

def _extract_string_field(text: str, field: str) -> str:
    match = re.search(rf'"{re.escape(field)}"\s*:\s*"((?:\\.|[^"\\])*)"', text, flags=re.S)
    if match:
        try:
            return json.loads(f'"{match.group(1)}"')
        except Exception:
            return match.group(1).encode("utf-8", "ignore").decode("utf-8", "ignore")

    # Fallback for truncated JSON where the closing quote is missing.
    loose_match = re.search(
        rf'"{re.escape(field)}"\s*:\s*"([^{{\]\[]*)$',
        text,
        flags=re.S,
    )
    if not loose_match:
        loose_match = re.search(
            rf'"{re.escape(field)}"\s*:\s*"(.+?)(?:,\s*"[A-Za-z_]+"|\s*[\r\n]|\s*$)',
            text,
            flags=re.S,
        )
    if not loose_match:
        return ""

    recovered = str(loose_match.group(1) or "")
    recovered = recovered.strip().rstrip(",").rstrip("}").rstrip("]").strip()
    recovered = recovered.replace('\\"', '"')
    return recovered.encode("utf-8", "ignore").decode("utf-8", "ignore").strip()

def _extract_int_field(text: str, field: str, default: int = 0) -> int:
    match = re.search(rf'"{re.escape(field)}"\s*:\s*(-?\d+)', text)
    if not match:
        return default
    try:
        return int(match.group(1))
    except Exception:
        return default

def _extract_score_partial(text: str) -> dict[str, int]:
    scores = {key: 0 for key in SKILL_KEYS}
    block_match = re.search(r'"score_partial"\s*:\s*\{(.*?)\}', text, flags=re.S)
    block = block_match.group(1) if block_match else text
    for key in SKILL_ORDER:
        scores[key] = _extract_int_field(block, key, 0)
    return scores

def _extract_skills(text: str, score_partial: dict[str, int]) -> dict[str, dict[str, Any]]:
    skills = empty_skills()
    for key in SKILL_ORDER:
        match = re.search(
            rf'"{re.escape(key)}"\s*:\s*\{{.*?"level"\s*:\s*(-?\d+)\s*,\s*"evidence"\s*:\s*"((?:\\.|[^"\\])*)"',
            text,
            flags=re.S,
        )
        if not match:
            skills[key]["level"] = score_partial.get(key, 0)
            continue
        try:
            level = max(0, min(5, int(match.group(1))))
        except Exception:
            level = score_partial.get(key, 0)
        evidence_raw = match.group(2)
        try:
            evidence = json.loads(f'"{evidence_raw}"')
        except Exception:
            evidence = evidence_raw
        skills[key]["level"] = level
        skills[key]["evidence"] = str(evidence).strip()[:MAX_EVIDENCE_CHARS]
    return skills

def _recover_interview_payload(text: str) -> dict[str, Any]:
    if not text:
        return {}

    phase = _extract_string_field(text, "phase").upper()
    if phase not in VALID_PHASES:
        return {}

    say = _extract_string_field(text, "say")
    if phase != "FINAL" and not say:
        return {}

    question_index = max(1, _extract_int_field(text, "question_index", 1))
    score_partial = _extract_score_partial(text)
    recovered = {
        "phase": phase,
        "question_index": question_index,
        "say": say,
        "score_partial": score_partial,
        "notes": [],
        "final_report": None,
    }
    return recovered
# ──────────────────────────────────────────────────────────────────────────────
# Helpers de normalisation par champ
# ──────────────────────────────────────────────────────────────────────────────
def empty_skills() -> dict[str, dict[str, Any]]:
    """Template vide pour les compétences (niveau 0, pas d'évidence)"""
    return {key: {"level": 0, "evidence": ""} for key in SKILL_KEYS}

def normalize_notes(notes: Any) -> list[str]:
    """Nettoie et limite la liste de notes"""
    if isinstance(notes, str):
        notes = [notes.strip()] if notes.strip() else []
    if not isinstance(notes, (list, tuple)):
        return []

    cleaned = [str(item).strip() for item in notes if str(item).strip()]
    return cleaned[:MAX_NOTES]

def normalize_score_partial(scores: Any) -> dict[str, int]:
    """Force les scores à être des entiers entre 0 et 5"""
    if not isinstance(scores, dict):
        return {k: 0 for k in SKILL_KEYS}

    normalized = {}
    for key in SKILL_KEYS:
        try:
            val = scores.get(key)
            normalized[key] = max(0, min(5, int(val))) if val is not None else 0
        except (TypeError, ValueError):
            normalized[key] = 0
    return normalized

def normalize_skills(
    skills_raw: Any,
    score_partial: dict[str, int]
) -> dict[str, dict[str, Any]]:
    """Normalise le bloc skills + fallback intelligent sur score_partial"""
    default = empty_skills()

    if isinstance(skills_raw, list):
        for item in skills_raw:
            key = str(item).strip().lower()
            if key in default:
                default[key]["level"] = max(default[key]["level"], score_partial.get(key, 0))
        return default

    if not isinstance(skills_raw, dict):
        for k in default:
            default[k]["level"] = score_partial.get(k, 0)
        return default

    normalized = empty_skills()
    for key in SKILL_KEYS:
        item = skills_raw.get(key, {})
        if isinstance(item, dict):
            try:
                level = int(item.get("level", score_partial.get(key, 0)))
                normalized[key]["level"] = max(0, min(5, level))
            except (TypeError, ValueError):
                normalized[key]["level"] = score_partial.get(key, 0)

            evid = str(item.get("evidence", "") or "").strip()
            normalized[key]["evidence"] = evid[:MAX_EVIDENCE_CHARS]
        else:
            normalized[key]["level"] = score_partial.get(key, 0)

    return normalized


def normalize_final_report(report: Any) -> dict | None:
    """Garde uniquement si c'est un dict (sinon None)"""
    return report if isinstance(report, dict) else None
# ──────────────────────────────────────────────────────────────────────────────
# Fonction principale : normalisation complète du payload
# ──────────────────────────────────────────────────────────────────────────────
def normalize_llm_payload(
    parsed: dict[str, Any],
    target_phase: str,
    last_index: int,
    strict_phase: bool = False,
) -> dict[str, Any]:
    """
    Normalise entièrement la réponse LLM :
    - Corrige phase si invalide
    - Assure question_index croissant
    - Nettoie say, skills, score_partial, notes, final_report
    - Applique des règles métier (pas de say vide hors FINAL, etc.)
    """
    normalized = dict(parsed) if parsed else {}

    # Phase
    phase = normalized.get("phase", target_phase)
    if phase not in VALID_PHASES:
        phase = target_phase
    normalized["phase"] = phase

    # Index de question (toujours croissant)
    try:
        q_index = int(normalized.get("question_index", last_index + 1))
    except (TypeError, ValueError):
        q_index = last_index + 1
    normalized["question_index"] = max(last_index + 1, q_index)

    # Champs normalisés
    normalized["score_partial"] = normalize_score_partial(normalized.get("score_partial"))
    normalized.pop("skills", None)
    normalized["notes"] = normalize_notes(normalized.get("notes"))
    normalized["final_report"] = normalize_final_report(normalized.get("final_report"))

    # say → chaîne vide → warning + fallback léger si phase non-FINAL
    say = str(normalized.get("say", "")).strip()
    if phase != "FINAL" and not say:
        logger.warning("say vide en phase non-FINAL → fallback message", extra={"phase": phase})
        say = "(Question non générée correctement – veuillez réessayer)"
    normalized["say"] = say

    # Option strict : lève une exception si phase forcée n'est pas respectée
    if strict_phase and normalized["phase"] != target_phase:
        raise ValueError(
            f"Phase retournée par LLM ({normalized['phase']}) ≠ phase cible ({target_phase})"
        )
    return normalized
