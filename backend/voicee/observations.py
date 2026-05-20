from __future__ import annotations

from typing import Any


def empty_audio_observations() -> dict[str, Any]:
    return {
        "utterance_count": 0,
        "total_duration_seconds": 0.0,
        "total_word_count": 0,
        "total_filler_count": 0,
        "speech_rate_sum": 0.0,
        "volume_sum": 0.0,
        "silence_ratio_sum": 0.0,
        "pause_count_sum": 0,
        "pitch_sum": 0.0,
        "pitch_sample_count": 0,
        "pitch_variation_sum": 0.0,
        "energy_labels": {},
        "pace_labels": {},
        "hesitation_labels": {},
    }


def _increment_counter(payload: dict[str, Any], key: str, value: str) -> None:
    label = str(value or "").strip().lower()
    if not label:
        return
    counters = dict(payload.get(key) or {})
    counters[label] = int(counters.get(label, 0) or 0) + 1
    payload[key] = counters


def _safe_average(total: float, count: int) -> float:
    return float(total) / max(1, count)


def update_audio_observations(current: dict[str, Any] | None, sample: dict[str, Any] | None) -> dict[str, Any]:
    merged = empty_audio_observations()
    if isinstance(current, dict):
        merged.update(current)
    payload = sample if isinstance(sample, dict) else {}

    merged["utterance_count"] = int(merged.get("utterance_count", 0) or 0) + 1
    merged["total_duration_seconds"] = float(merged.get("total_duration_seconds", 0.0) or 0.0) + float(
        payload.get("duration_seconds", 0.0) or 0.0
    )
    merged["total_word_count"] = int(merged.get("total_word_count", 0) or 0) + int(payload.get("word_count", 0) or 0)
    merged["total_filler_count"] = int(merged.get("total_filler_count", 0) or 0) + int(
        payload.get("filler_count", 0) or 0
    )
    merged["speech_rate_sum"] = float(merged.get("speech_rate_sum", 0.0) or 0.0) + float(
        payload.get("speech_rate_wpm", 0.0) or 0.0
    )
    merged["volume_sum"] = float(merged.get("volume_sum", 0.0) or 0.0) + float(
        payload.get("volume_score", 0.0) or 0.0
    )
    merged["silence_ratio_sum"] = float(merged.get("silence_ratio_sum", 0.0) or 0.0) + float(
        payload.get("silence_ratio", 0.0) or 0.0
    )
    merged["pause_count_sum"] = int(merged.get("pause_count_sum", 0) or 0) + int(payload.get("pause_count", 0) or 0)

    pitch_hz = float(payload.get("pitch_hz", 0.0) or 0.0)
    pitch_variation_hz = float(payload.get("pitch_variation_hz", 0.0) or 0.0)
    if pitch_hz > 0:
        merged["pitch_sum"] = float(merged.get("pitch_sum", 0.0) or 0.0) + pitch_hz
        merged["pitch_sample_count"] = int(merged.get("pitch_sample_count", 0) or 0) + 1
        merged["pitch_variation_sum"] = float(merged.get("pitch_variation_sum", 0.0) or 0.0) + pitch_variation_hz

    _increment_counter(merged, "energy_labels", str(payload.get("energy_label", "") or ""))
    _increment_counter(merged, "pace_labels", str(payload.get("pace_label", "") or ""))
    _increment_counter(merged, "hesitation_labels", str(payload.get("hesitation_label", "") or ""))
    return merged


def _top_label(payload: dict[str, Any], key: str) -> str:
    counters = dict(payload.get(key) or {})
    best_label = ""
    best_count = -1
    for label, raw_count in counters.items():
        try:
            count = int(raw_count)
        except Exception:
            count = 0
        if count > best_count:
            best_label = str(label).strip()
            best_count = count
    return best_label


def build_audio_metrics(observations: dict[str, Any] | None, response_language: str = "fr") -> dict[str, Any]:
    payload = observations if isinstance(observations, dict) else {}
    utterance_count = int(payload.get("utterance_count", 0) or 0)
    total_words = int(payload.get("total_word_count", 0) or 0)
    total_fillers = int(payload.get("total_filler_count", 0) or 0)
    pitch_count = int(payload.get("pitch_sample_count", 0) or 0)
    total_duration = float(payload.get("total_duration_seconds", 0.0) or 0.0)

    avg_speech_rate = round(_safe_average(float(payload.get("speech_rate_sum", 0.0) or 0.0), utterance_count), 1)
    avg_volume = round(_safe_average(float(payload.get("volume_sum", 0.0) or 0.0), utterance_count), 1)
    avg_silence_pct = round(_safe_average(float(payload.get("silence_ratio_sum", 0.0) or 0.0), utterance_count) * 100, 1)
    avg_pause_count = round(_safe_average(float(payload.get("pause_count_sum", 0) or 0), utterance_count), 1)
    avg_utterance_duration_seconds = round(_safe_average(total_duration, utterance_count), 1) if utterance_count else 0.0
    pause_rate_per_min = (
        round((avg_pause_count * 60.0) / max(avg_utterance_duration_seconds, 1.0), 1)
        if avg_utterance_duration_seconds > 0
        else 0.0
    )
    avg_pitch_hz = round(_safe_average(float(payload.get("pitch_sum", 0.0) or 0.0), pitch_count), 1) if pitch_count else 0.0
    avg_pitch_variation_hz = (
        round(_safe_average(float(payload.get("pitch_variation_sum", 0.0) or 0.0), pitch_count), 1) if pitch_count else 0.0
    )
    filler_density = round((total_fillers / max(1, total_words)) * 100, 1)

    is_en = str(response_language).strip().lower() == "en"
    confidence_note = (
        "Moderate confidence: audio observations are based on browser-side capture and transcript-derived metrics."
        if is_en
        else "Confiance moyenne : les observations vocales reposent sur la capture navigateur et des metriques derivees de la transcription."
    )
    if utterance_count <= 1:
        confidence_note = (
            "Low confidence: too few spoken samples were captured."
            if is_en
            else "Confiance faible : trop peu d'echantillons vocaux ont ete captures."
        )

    return {
        "utterance_count": utterance_count,
        "total_duration_seconds": round(total_duration, 1),
        "avg_utterance_duration_seconds": avg_utterance_duration_seconds,
        "speech_rate_wpm_avg": avg_speech_rate,
        "volume_score_avg": avg_volume,
        "silence_pct_avg": avg_silence_pct,
        "pause_count_avg": avg_pause_count,
        "pause_rate_per_min_avg": pause_rate_per_min,
        "pitch_hz_avg": avg_pitch_hz,
        "pitch_variation_hz_avg": avg_pitch_variation_hz,
        "filler_count_total": total_fillers,
        "filler_density_pct": filler_density,
        "dominant_energy": _top_label(payload, "energy_labels"),
        "dominant_pace": _top_label(payload, "pace_labels"),
        "dominant_hesitation": _top_label(payload, "hesitation_labels"),
        "confidence_note": confidence_note,
    }


def build_audio_flags(observations: dict[str, Any] | None, response_language: str = "fr") -> list[str]:
    metrics = build_audio_metrics(observations, response_language)
    flags: list[str] = []
    if metrics["utterance_count"] <= 1:
        return ["analyse_vocale_insuffisante"]
    if metrics["speech_rate_wpm_avg"] >= 170:
        flags.append("debit_rapide")
    if 0 < metrics["speech_rate_wpm_avg"] <= 105:
        flags.append("debit_mesure")
    if metrics["silence_pct_avg"] >= 24 or metrics["pause_rate_per_min_avg"] >= 12:
        flags.append("pauses_marquees")
    if metrics["filler_density_pct"] >= 2.5 or metrics["dominant_hesitation"] == "noticeable":
        flags.append("hesitations_verbales")
    if metrics["volume_score_avg"] <= 28:
        flags.append("energie_vocale_limitee")
    if 35 <= metrics["volume_score_avg"] <= 70 and metrics["silence_pct_avg"] <= 18:
        flags.append("delivery_vocal_stable")
    if metrics["volume_score_avg"] >= 66 and metrics["pitch_variation_hz_avg"] >= 22 and metrics["silence_pct_avg"] <= 16:
        flags.append("enthousiasme_vocal_soutenu")
    elif metrics["volume_score_avg"] >= 48 and metrics["pitch_variation_hz_avg"] >= 12:
        flags.append("enthousiasme_vocal_mesure")
    if metrics["speech_rate_wpm_avg"] >= 165 and (
        metrics["silence_pct_avg"] >= 20
        or metrics["filler_density_pct"] >= 2.5
        or metrics["pause_rate_per_min_avg"] >= 12
    ):
        flags.append("tension_vocale_apparente")
    return flags


def build_audio_signals(observations: dict[str, Any] | None, response_language: str = "fr") -> list[str]:
    metrics = build_audio_metrics(observations, response_language)
    flags = build_audio_flags(observations, response_language)
    is_en = str(response_language).strip().lower() == "en"

    if metrics["utterance_count"] <= 1:
        return [
            "Audio analysis remains limited because too few spoken samples were captured."
            if is_en
            else "L'analyse vocale reste limitee car trop peu d'echantillons ont ete captures."
        ]

    signals: list[str] = []
    if "delivery_vocal_stable" in flags:
        signals.append(
            "Vocal delivery remained globally stable."
            if is_en
            else "La delivery vocale est restee globalement stable."
        )
    if "debit_rapide" in flags:
        signals.append(
            f"Speech pace appeared fast at about {metrics['speech_rate_wpm_avg']} words per minute."
            if is_en
            else f"Le debit de parole a paru rapide, autour de {metrics['speech_rate_wpm_avg']} mots par minute."
        )
    elif "debit_mesure" in flags:
        signals.append(
            f"Speech pace appeared measured at about {metrics['speech_rate_wpm_avg']} words per minute."
            if is_en
            else f"Le debit de parole a paru mesure, autour de {metrics['speech_rate_wpm_avg']} mots par minute."
        )
    if "pauses_marquees" in flags:
        signals.append(
            "Pauses and silences were noticeable across several answers."
            if is_en
            else "Les pauses et silences etaient perceptibles sur plusieurs reponses."
        )
    if "hesitations_verbales" in flags:
        signals.append(
            f"Verbal hesitation markers remained occasional to moderate ({metrics['filler_count_total']} fillers captured)."
            if is_en
            else f"Les marqueurs d'hesitation verbale sont restes occasionnels a moderes ({metrics['filler_count_total']} fillers detectes)."
        )
    if "energie_vocale_limitee" in flags:
        signals.append(
            "Vocal energy remained rather contained."
            if is_en
            else "L'energie vocale est restee plutot contenue."
        )
    if "enthousiasme_vocal_soutenu" in flags:
        signals.append(
            "Vocal enthusiasm appeared sustained, with clear energy and variation."
            if is_en
            else "L'enthousiasme vocal a paru soutenu, avec une energie et une variation bien presentes."
        )
    elif "enthousiasme_vocal_mesure" in flags:
        signals.append(
            "Vocal enthusiasm appeared present but measured."
            if is_en
            else "L'enthousiasme vocal a paru present mais mesure."
        )
    if "tension_vocale_apparente" in flags:
        signals.append(
            "Some apparent vocal tension cues were observed and should remain secondary."
            if is_en
            else "Quelques indices apparents de tension vocale ont ete observes et doivent rester secondaires."
        )
    if metrics["pitch_hz_avg"] > 0:
        signals.append(
            f"Average pitch stayed around {metrics['pitch_hz_avg']} Hz."
            if is_en
            else f"Le pitch moyen est reste autour de {metrics['pitch_hz_avg']} Hz."
        )
    deduped: list[str] = []
    seen: set[str] = set()
    for signal in signals:
        if signal not in seen:
            deduped.append(signal)
            seen.add(signal)
    return deduped[:5]


def build_audio_llm_context(observations: dict[str, Any] | None, response_language: str = "fr") -> dict[str, Any]:
    metrics = build_audio_metrics(observations, response_language)
    return {
        "metrics": metrics,
        "signals": build_audio_signals(observations, response_language),
        "heuristic_flags": build_audio_flags(observations, response_language),
        "confidence_note": metrics["confidence_note"],
    }
