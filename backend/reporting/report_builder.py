from __future__ import annotations

import unicodedata
import re
from typing import Any, Callable

from interview_ai.constants import SKILL_KEYS
from interview_ai.prompts import build_chat_messages, build_cv_summary


RequestJsonFn = Callable[..., dict[str, Any]]

ENGLISH_HINTS = ("candidate ", "shows ", "moderate ", "focus on ", "encourage ", "maintain ", "practice ")
FRENCH_HINTS = (" candidat", " montre", " technique", " entretien", " recommande", " conseil")
TRIVIAL_LAUNCH_MESSAGES = {
    "je suis prete",
    "je suis pret",
    "je suis prete de commencer",
    "je suis pret de commencer",
    "prete",
    "pret",
    "prete de commencer",
    "pret de commencer",
    "ready",
    "ready to start",
    "i am ready",
    "i am ready to start",
    "im ready",
    "im ready to start",
    "oui",
    "ok",
    "d accord",
    "bonjour",
}


def _looks_like_wrong_language(text: str, response_language: str) -> bool:
    lowered = f" {str(text or '').strip().lower()} "
    if not lowered.strip():
        return True
    if response_language == "fr":
        en_hits = sum(1 for marker in ENGLISH_HINTS if marker in lowered)
        fr_hits = sum(1 for marker in FRENCH_HINTS if marker in lowered)
        return en_hits > fr_hits
    return False


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.replace("’", "'").replace("'", " ")
    return " ".join(normalized.lower().split()).strip()


def _is_trivial_launch_message(text: str) -> bool:
    return _normalize_text(text) in TRIVIAL_LAUNCH_MESSAGES


def _fallback_summary(
    *,
    response_language: str,
    strengths: list[str],
    improvement_points: list[str],
) -> str:
    if response_language == "en":
        strengths_part = strengths[0] if strengths else "The candidate shows a usable technical base."
        improvement_part = improvement_points[0] if improvement_points else "Further technical assessment may help refine the evaluation."
        return f"{strengths_part} {improvement_part}"

    strengths_part = strengths[0] if strengths else "Le candidat montre une base technique exploitable."
    improvement_part = improvement_points[0] if improvement_points else "Un echange technique complementaire permettrait d'affiner l'evaluation."
    return f"{strengths_part} {improvement_part}"


def _fallback_advice(response_language: str) -> list[str]:
    if response_language == "en":
        return [
            "Use more concise and structured examples.",
            "Link each answer to a concrete impact or outcome.",
        ]
    return [
        "Donner des exemples plus concis et structures.",
        "Relier chaque reponse a un impact ou un resultat concret.",
    ]


def _normalize_advice_item(item: str, response_language: str) -> str:
    text = str(item or "").strip()
    if not text:
        return ""

    if response_language == "fr":
        lowered = text.lower()
        direct_patterns = [
            (r"^encourager le candidat\s+[aà]\s+(.+)$", "Nous vous conseillons de {body}"),
            (r"^inciter le candidat\s+[aà]\s+(.+)$", "Nous vous conseillons de {body}"),
            (r"^sugg[ée]rer\s+(.+)$", "Pensez a {body}"),
            (r"^proposer\s+(.+)$", "Pensez a {body}"),
        ]
        for pattern, template in direct_patterns:
            match = re.match(pattern, lowered, flags=re.IGNORECASE)
            if match:
                body = match.group(1).strip(" .;:")
                text = template.format(body=body)
                break

    else:
        lowered = text.lower()
        direct_patterns = [
            (r"^encourage the candidate to\s+(.+)$", "We recommend that you {body}"),
            (r"^suggest\s+(.+)$", "Consider {body}"),
            (r"^propose\s+(.+)$", "Consider {body}"),
        ]
        for pattern, template in direct_patterns:
            match = re.match(pattern, lowered, flags=re.IGNORECASE)
            if match:
                body = match.group(1).strip(" .;:")
                text = template.format(body=body)
                break

    text = text.strip()
    if text and text[-1] not in ".!?":
        text += "."
    return text[:1].upper() + text[1:] if text else ""


def _normalize_report_item(item: str) -> str:
    text = str(item or "").strip()
    if not text:
        return ""
    if text and text[-1] not in ".!?":
        text += "."
    return text[:1].upper() + text[1:] if text else ""


def generate_final_report_text(
    *,
    request_json: RequestJsonFn,
    competencies: dict[str, int],
    strengths: list[str],
    improvement_points: list[str],
    visual_context: dict[str, Any],
    audio_context: dict[str, Any],
    cv_profile: dict[str, Any],
    turns: list[dict[str, Any]],
    response_language: str = "fr",
) -> dict[str, Any]:
    history_lines: list[str] = []
    for turn in turns[-6:]:
        if not isinstance(turn, dict):
            continue
        question = str(turn.get("say", "")).strip()[:140]
        answer = str(turn.get("candidate_text", "")).strip()[:220]
        if _is_trivial_launch_message(answer):
            continue
        if question or answer:
            history_lines.append(f"Q: {question} -> R: {answer}")

    resolved_visual_context = visual_context if isinstance(visual_context, dict) else {}
    visual_metrics = resolved_visual_context.get("metrics") or {}
    visual_signals = resolved_visual_context.get("signals") or []
    heuristic_flags = resolved_visual_context.get("heuristic_flags") or []
    confidence_note = str(resolved_visual_context.get("confidence_note", "") or "").strip()
    resolved_audio_context = audio_context if isinstance(audio_context, dict) else {}
    audio_metrics = resolved_audio_context.get("metrics") or {}
    audio_signals = resolved_audio_context.get("signals") or []
    audio_flags = resolved_audio_context.get("heuristic_flags") or []
    audio_confidence_note = str(resolved_audio_context.get("confidence_note", "") or "").strip()

    if response_language == "en":
        history_text = "\n".join(history_lines) if history_lines else "No usable interview history"
        cv_summary = build_cv_summary(cv_profile) if isinstance(cv_profile, dict) else "Detailed CV profile unavailable."
        system = (
            "You are a senior technical interviewer. "
            "Use competency scores, CV context, and interview excerpts to write a short technical interview report. "
            "Do not include visual, vocal, or emotional insight signals in this final technical summary. "
            "Those signals belong to a separate insights section and must stay out of the synthesis. "
            "Reply ONLY with a valid JSON object."
        )
        user = (
            "Generate a final technical interview report with this structure:\n"
            '- "summary": 3 to 5 sentences in English.\n'
            '- "strengths": an array of 2 to 3 tailored strengths.\n'
            '- "improvement_points": an array of 2 to 3 tailored development areas.\n'
            '- "advice": an array of 2 to 3 practical interview tips.\n\n'
            '- "dimension_actions": an object with the key "question_score", containing one tailored recommended action.\n\n'
            "Rules:\n"
            "- Base the summary, strengths, improvement_points, and advice only on the CV, the interview content, and the competency scores.\n"
            "- Do not mention visual, vocal, emotional, stress, posture, or face-analysis cues in the summary or advice.\n"
            "- Write the advice directly to the candidate, using 'you', not 'the candidate'.\n"
            "- Write strengths and improvement_points in technical interviewer language, tailored to this candidate.\n"
            "- Each dimension action must match the corresponding competency and remain specific, practical, and personalized to this candidate.\n"
            "- Advice must be practical, clear, and directly actionable.\n\n"
            "Context:\n"
            f"- Competency scores: {competencies}\n"
            f"CV summary:\n{cv_summary}\n\n"
            f"Interview excerpts:\n{history_text}\n\n"
            'Return ONLY JSON in the form {"summary":"...","strengths":["..."],"improvement_points":["..."],"advice":["..."],"dimension_actions":{"question_score":"..."}}.'
        )
    else:
        history_text = "\n".join(history_lines) if history_lines else "Aucun historique exploitable"
        cv_summary = build_cv_summary(cv_profile) if isinstance(cv_profile, dict) else "Profil CV non disponible en detail."
        system = (
            "Tu es un interviewer technique senior. "
            "A partir des scores, du CV et d'extraits d'entretien, redige un court rapport technique nuance et prudent. "
            "N'inclus jamais les signaux visuels, vocaux ou emotionnels dans cette synthese technique finale. "
            "Ces signaux appartiennent a une section insights separee et doivent rester hors du rapport de synthese. "
            "Reponds UNIQUEMENT avec un objet JSON valide."
        )
        user = (
            "Genere un rapport final d'entretien technique avec cette structure :\n"
            '- "summary": 3 a 5 phrases en francais.\n'
            '- "strengths": un tableau de 2 a 3 points forts personnalises.\n'
            "- \"improvement_points\": un tableau de 2 a 3 axes d'amelioration personnalises.\n"
            '- "advice": un tableau de 2 a 3 conseils pratiques.\n\n'
            '- "dimension_actions": un objet avec la cle "question_score", contenant une action recommandee personnalisee.\n\n'
            "Regles:\n"
            "- Base la synthese, les strengths, les improvement_points et les conseils uniquement sur le CV, le contenu de l'entretien et les scores de competences.\n"
            "- Ne mentionne pas les signaux visuels, vocaux, emotionnels, le stress, la posture ou l'analyse du visage dans la synthese ni dans les conseils.\n"
            "- Redige les conseils en parlant directement au candidat avec 'vous', jamais avec 'le candidat'.\n"
            "- Redige les strengths et improvement_points comme un interviewer technique, de maniere personnalisee pour ce candidat.\n"
            "- Chaque action par dimension doit correspondre a la competence concernee et rester concrete, utile et personnalisee pour ce candidat.\n"
            "- Les conseils doivent etre pratiques, clairs et actionnables.\n\n"
            "Contexte :\n"
            f"- Scores par competence: {competencies}\n"
            f"Resume CV:\n{cv_summary}\n\n"
            f"Extraits d'entretien:\n{history_text}\n\n"
            'Reponds UNIQUEMENT avec un JSON de la forme {"summary":"...","strengths":["..."],"improvement_points":["..."],"advice":["..."],"dimension_actions":{"question_score":"..."}}.'
        )

    parsed = request_json(
        messages=build_chat_messages(
            system_content=system,
            user_content=user,
        ),
        max_tokens=420,
        temperature=0.25,
        log_mode="final_report_prompt_json",
        phase="FINAL",
    )
    summary = str(parsed.get("summary", "") or "").strip()
    llm_strengths = [_normalize_report_item(str(item)) for item in (parsed.get("strengths") or []) if str(item).strip()]
    llm_strengths = [item for item in llm_strengths if item]
    llm_improvement_points = [
        _normalize_report_item(str(item))
        for item in (parsed.get("improvement_points") or [])
        if str(item).strip()
    ]
    llm_improvement_points = [item for item in llm_improvement_points if item]
    raw_dimension_actions = parsed.get("dimension_actions") if isinstance(parsed.get("dimension_actions"), dict) else {}
    llm_dimension_actions = {
        key: _normalize_advice_item(str(raw_dimension_actions.get(key, "")), response_language)
        for key in SKILL_KEYS
        if str(raw_dimension_actions.get(key, "")).strip()
    }
    advice = [_normalize_advice_item(str(item), response_language) for item in (parsed.get("advice") or []) if str(item).strip()]
    advice = [item for item in advice if item]

    if _looks_like_wrong_language(summary, response_language):
        parsed = request_json(
            messages=build_chat_messages(
                system_content=system,
                user_content=(
                    f"{user}\n\n"
                    f"Correction stricte : la reponse doit etre entierement en "
                    f"{'anglais' if response_language == 'en' else 'francais'}."
                ),
            ),
            max_tokens=420,
            temperature=0.15,
            log_mode="final_report_prompt_json_retry_language",
            phase="FINAL",
        )
        summary = str(parsed.get("summary", "") or "").strip()
        llm_strengths = [_normalize_report_item(str(item)) for item in (parsed.get("strengths") or []) if str(item).strip()]
        llm_strengths = [item for item in llm_strengths if item]
        llm_improvement_points = [
            _normalize_report_item(str(item))
            for item in (parsed.get("improvement_points") or [])
            if str(item).strip()
        ]
        llm_improvement_points = [item for item in llm_improvement_points if item]
        raw_dimension_actions = parsed.get("dimension_actions") if isinstance(parsed.get("dimension_actions"), dict) else {}
        llm_dimension_actions = {
            key: _normalize_advice_item(str(raw_dimension_actions.get(key, "")), response_language)
            for key in SKILL_KEYS
            if str(raw_dimension_actions.get(key, "")).strip()
        }
        advice = [_normalize_advice_item(str(item), response_language) for item in (parsed.get("advice") or []) if str(item).strip()]
        advice = [item for item in advice if item]

    if _looks_like_wrong_language(summary, response_language):
        parsed["summary"] = _fallback_summary(
            response_language=response_language,
            strengths=strengths,
            improvement_points=improvement_points,
        )
    parsed["strengths"] = llm_strengths[:3]
    parsed["improvement_points"] = llm_improvement_points[:3] or improvement_points[:3]
    parsed["dimension_actions"] = llm_dimension_actions
    parsed["recommendations"] = []
    if not advice or any(_looks_like_wrong_language(item, response_language) for item in advice):
        parsed["advice"] = _fallback_advice(response_language)

    return parsed
