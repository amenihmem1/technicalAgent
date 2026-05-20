from __future__ import annotations

from typing import Any, Callable

from interview_ai.prompts import build_chat_messages


RequestJsonFn = Callable[..., dict[str, Any]]

ENGLISH_HINTS = ("candidate ", "shows ", "moderate ", "focus on ", "encourage ", "maintain ", "practice ")
FRENCH_HINTS = (" candidat", " montre", " technique", " entretien", " recommande", " conseil")


def _looks_like_wrong_language(text: str, response_language: str) -> bool:
    lowered = f" {str(text or '').strip().lower()} "
    if not lowered.strip():
        return True
    if response_language == "fr":
        en_hits = sum(1 for marker in ENGLISH_HINTS if marker in lowered)
        fr_hits = sum(1 for marker in FRENCH_HINTS if marker in lowered)
        return en_hits > fr_hits
    return False


def generate_insights_advice_text(
    *,
    request_json: RequestJsonFn,
    visual_context: dict[str, Any],
    audio_context: dict[str, Any],
    stress_context: dict[str, Any],
    response_language: str = "fr",
) -> dict[str, Any]:
    resolved_visual_context = visual_context if isinstance(visual_context, dict) else {}
    resolved_audio_context = audio_context if isinstance(audio_context, dict) else {}
    resolved_stress_context = stress_context if isinstance(stress_context, dict) else {}

    visual_metrics = resolved_visual_context.get("metrics") or {}
    visual_signals = resolved_visual_context.get("signals") or []
    visual_flags = resolved_visual_context.get("heuristic_flags") or []
    visual_confidence_note = str(resolved_visual_context.get("confidence_note", "") or "").strip()

    audio_metrics = resolved_audio_context.get("metrics") or {}
    audio_signals = resolved_audio_context.get("signals") or []
    audio_flags = resolved_audio_context.get("heuristic_flags") or []
    audio_confidence_note = str(resolved_audio_context.get("confidence_note", "") or "").strip()

    stress_score = resolved_stress_context.get("score", 0)
    stress_band = str(resolved_stress_context.get("band", "") or "").strip()
    stress_summary = str(resolved_stress_context.get("summary", "") or "").strip()
    stress_factors = resolved_stress_context.get("factors") or []
    stress_confidence_note = str(resolved_stress_context.get("confidence_note", "") or "").strip()

    if response_language == "en":
        system = (
            "You are a warm interview coach. "
            "Your task is to write kind, constructive, non-severe advice based ONLY on visual, vocal, and emotional insight signals. "
            "Do not write an HR evaluation. Do not talk about hiring decisions. "
            "Never state anxiety, stress, sadness, or dishonesty as psychological facts. "
            "Use supportive and careful wording. Reply ONLY with valid JSON."
        )
        user = (
            "Generate a gentle insights coaching card with this JSON structure:\n"
            '{"thank_you":"...","summary":["..."],"strengths":["..."],"improvements":["..."],"next_steps":["..."],"closing":"..."}\n\n'
            "Rules:\n"
            "- Base the advice ONLY on the 3 dashboards: visual, vocal, emotional reading.\n"
            "- Do not mention hiring recommendation, reject, or fit.\n"
            "- Keep a psychologically safe tone.\n"
            "- Improvements must sound encouraging, never harsh.\n"
            "- next_steps should help with the next interview.\n"
            "- 2 items max in summary, 2 to 3 in strengths, 2 to 3 in improvements, 2 to 3 in next_steps.\n\n"
            "Visual context:\n"
            f"- metrics: {visual_metrics or {'sample_count': 0}}\n"
            f"- signals: {visual_signals or ['No visual signal captured']}\n"
            f"- flags: {visual_flags or ['none']}\n"
            f"- confidence note: {visual_confidence_note or 'No visual confidence note'}\n\n"
            "Audio context:\n"
            f"- metrics: {audio_metrics or {'utterance_count': 0}}\n"
            f"- signals: {audio_signals or ['No audio signal captured']}\n"
            f"- flags: {audio_flags or ['none']}\n"
            f"- confidence note: {audio_confidence_note or 'No audio confidence note'}\n\n"
            "Emotional reading:\n"
            f"- stress score: {stress_score}\n"
            f"- stress band: {stress_band or 'n/a'}\n"
            f"- summary: {stress_summary or 'No stress summary'}\n"
            f"- factors: {stress_factors or ['none']}\n"
            f"- confidence note: {stress_confidence_note or 'No stress confidence note'}\n\n"
            "Return ONLY JSON."
        )
    else:
        system = (
            "Tu es un coach d'entretien bienveillant. "
            "Ta mission est de rediger des conseils doux, constructifs et non severes, "
            "a partir UNIQUEMENT des signaux visuels, vocaux et emotionnels. "
            "Tu ne rediges pas une evaluation de recrutement. Tu ne parles pas de decision d'embauche. "
            "N'affirme jamais un etat psychologique comme un fait etabli. "
            "Utilise un ton prudent, encourageant et rassurant. Reponds UNIQUEMENT avec un JSON valide."
        )
        user = (
            "Genere une carte de conseils insights avec cette structure JSON :\n"
            '{"thank_you":"...","summary":["..."],"strengths":["..."],"improvements":["..."],"next_steps":["..."],"closing":"..."}\n\n'
            "Regles :\n"
            "- Base-toi UNIQUEMENT sur les 3 tableaux : visuel, vocal, lecture emotionnelle.\n"
            "- Ne parle pas de recommandation d'embauche, de rejet ou d'adequation au poste.\n"
            "- Garde un ton psychologiquement securisant.\n"
            "- Les axes d'amelioration doivent rester encourageants, jamais durs.\n"
            "- next_steps doit aider pour le prochain entretien.\n"
            "- 2 elements max dans summary, 2 a 3 dans strengths, 2 a 3 dans improvements, 2 a 3 dans next_steps.\n\n"
            "Contexte visuel :\n"
            f"- metriques : {visual_metrics or {'sample_count': 0}}\n"
            f"- signaux : {visual_signals or ['Aucun signal visuel capture']}\n"
            f"- flags : {visual_flags or ['aucun']}\n"
            f"- note de confiance : {visual_confidence_note or 'Aucune note de confiance visuelle'}\n\n"
            "Contexte vocal :\n"
            f"- metriques : {audio_metrics or {'utterance_count': 0}}\n"
            f"- signaux : {audio_signals or ['Aucun signal vocal capture']}\n"
            f"- flags : {audio_flags or ['aucun']}\n"
            f"- note de confiance : {audio_confidence_note or 'Aucune note de confiance vocale'}\n\n"
            "Lecture emotionnelle :\n"
            f"- score de stress : {stress_score}\n"
            f"- niveau : {stress_band or 'n/a'}\n"
            f"- synthese : {stress_summary or 'Aucune synthese'}\n"
            f"- facteurs : {stress_factors or ['aucun']}\n"
            f"- note de confiance : {stress_confidence_note or 'Aucune note de confiance emotionnelle'}\n\n"
            "Reponds UNIQUEMENT avec le JSON."
        )

    base_messages = build_chat_messages(system_content=system, user_content=user)
    parsed = request_json(
        messages=base_messages,
        max_tokens=420,
        temperature=0.3,
        log_mode="insights_advice_prompt_json",
        phase="FINAL",
    )

    thank_you = str(parsed.get("thank_you", "") or "").strip()
    summary = [str(item).strip() for item in (parsed.get("summary") or []) if str(item).strip()]
    strengths = [str(item).strip() for item in (parsed.get("strengths") or []) if str(item).strip()]
    improvements = [str(item).strip() for item in (parsed.get("improvements") or []) if str(item).strip()]
    next_steps = [str(item).strip() for item in (parsed.get("next_steps") or []) if str(item).strip()]
    closing = str(parsed.get("closing", "") or "").strip()

    wrong_language = any(
        _looks_like_wrong_language(text, response_language)
        for text in [thank_you, closing, *summary, *strengths, *improvements, *next_steps]
        if str(text).strip()
    )

    if wrong_language:
        correction = (
            "Strict correction: the whole JSON response must be fully in English."
            if response_language == "en"
            else "Correction stricte : tout le JSON doit etre entierement en francais."
        )
        parsed = request_json(
            messages=base_messages + [{"role": "user", "content": correction}],
            max_tokens=420,
            temperature=0.15,
            log_mode="insights_advice_prompt_json_retry_language",
            phase="FINAL",
        )
        thank_you = str(parsed.get("thank_you", "") or "").strip()
        summary = [str(item).strip() for item in (parsed.get("summary") or []) if str(item).strip()]
        strengths = [str(item).strip() for item in (parsed.get("strengths") or []) if str(item).strip()]
        improvements = [str(item).strip() for item in (parsed.get("improvements") or []) if str(item).strip()]
        next_steps = [str(item).strip() for item in (parsed.get("next_steps") or []) if str(item).strip()]
        closing = str(parsed.get("closing", "") or "").strip()

    parsed["thank_you"] = thank_you
    parsed["summary"] = summary[:2]
    parsed["strengths"] = strengths[:3]
    parsed["improvements"] = improvements[:3]
    parsed["next_steps"] = next_steps[:3]
    parsed["closing"] = closing
    return parsed
