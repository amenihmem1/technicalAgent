from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
import importlib
from importlib.util import find_spec
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Protocol
from zipfile import ZIP_DEFLATED, ZipFile


# ---------------------------------------------------------------------------
# Core data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class EmotionAnalysis:
    provider: str
    ready: bool
    summary: str
    label: str = ""
    confidence: float | None = None
    metadata: dict[str, Any] | None = None


class EmotionAnalyzer(Protocol):
    provider: str

    def describe(self) -> EmotionAnalysis: ...
    def analyze_image_bytes(
        self,
        raw_bytes: bytes,
        *,
        frame_hint: dict[str, Any] | None = None,
    ) -> EmotionAnalysis: ...


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ACTIVE_EMOTION_PROVIDER = "custom"
_MODEL_PROBE_VARIATION_MIN = 0.02
_MODEL_PROBE_NOISE_SEED = 42
_MIN_REPORTABLE_CONFIDENCE = 0.60
_MIN_REPORTABLE_MARGIN = 0.18
_MAX_STRONG_RUNNER_UP = 0.25
_FACE_CROP_PAD_X = 0.16
_FACE_CROP_PAD_TOP = 0.22
_FACE_CROP_PAD_BOTTOM = 0.10
_FACE_REDETECT_PAD_X = 0.30
_FACE_REDETECT_PAD_TOP = 0.34
_FACE_REDETECT_PAD_BOTTOM = 0.18
_MIN_REPORTABLE_FRAME_QUALITY = 0.62
_MIN_REPORTABLE_FACE_AREA = 0.05


def _allow_unverified_custom_model() -> bool:
    raw = os.getenv("CUSTOM_EMOTION_ALLOW_UNVERIFIED")
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _use_raw_model_only_mode() -> bool:
    raw = os.getenv("CUSTOM_EMOTION_RAW_MODEL_ONLY")
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Observation helpers
# ---------------------------------------------------------------------------

def empty_visual_observations() -> dict[str, Any]:
    return {
        "sample_count": 0,
        "face_detected_count": 0,
        "centered_count": 0,
        "looking_forward_count": 0,
        "multiple_faces_count": 0,
        "stable_posture_count": 0,
        "smile_count": 0,
        "expressions": {},
        "postures": {},
        "object_sample_count": 0,
        "object_counts": {},
        "object_confidence_totals": {},
        "providers": {},
    }


def _active_provider_names() -> set[str]:
    return {ACTIVE_EMOTION_PROVIDER}


def _filter_active_providers(raw_providers: Any) -> dict[str, Any]:
    if not isinstance(raw_providers, dict):
        return {}
    active = _active_provider_names()
    return {
        str(name): dict(payload or {})
        for name, payload in raw_providers.items()
        if str(name).strip().lower() in active
    }


# ---------------------------------------------------------------------------
# Label normalization
# ---------------------------------------------------------------------------

def _canonical_model_label(raw_label: str) -> str:
    """
    Keep labels faithful to the model.
    Only normalize near-synonyms, never convert to business buckets.
    """
    label = (raw_label or "").strip().lower().replace("_", " ").replace("-", " ")
    if not label:
        return ""

    aliases = {
        "joy": "happy",
        "smile": "happy",
        "smiling": "happy",
        "calm": "neutral",
        "anger": "angry",
        "sadness": "sad",
        "surprised": "surprise",
        "fearful": "fear",
    }
    return aliases.get(label, label)


def _normalize_emotion_breakdown_label(raw_label: str) -> str:
    return _canonical_model_label(raw_label)


def _soft_visual_label(raw_label: str) -> str:
    """
    Separate visual interpretation buckets for UI / RH heuristics only.
    This must NOT be used as the main emotion truth.
    """
    label = _canonical_model_label(raw_label)
    if not label:
        return ""
    if label == "uncertain":
        return ""

    if label in {"neutral"}:
        return "neutral"
    if label in {"happy"}:
        return "engaged"
    if label in {"surprise"}:
        return "alert"
    if label in {"fear"}:
        return "tension cues"
    if label in {"sad"}:
        return "low affect"
    if label in {"angry", "disgust"}:
        return "tense"
    return label


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------

def _format_percent(value: float) -> int:
    return max(0, min(100, round(value * 100)))


def _safe_ratio(count: int | float, total: int | float) -> float:
    try:
        denom = float(total)
    except Exception:
        denom = 0.0
    if denom <= 0:
        return 0.0
    try:
        return max(0.0, float(count) / denom)
    except Exception:
        return 0.0


def _top_counter_label(counter_payload: dict[str, Any]) -> str:
    best_label, best_count = "", -1
    for label, raw_count in counter_payload.items():
        try:
            count = float(raw_count)
        except Exception:
            count = 0.0
        if count > best_count:
            best_label, best_count = str(label).strip(), count
    return best_label


def _bucket_visual_enthusiasm(ratio: float, response_language: str) -> str:
    is_en = str(response_language).strip().lower() == "en"
    if ratio >= 0.68:
        return "high" if is_en else "eleve"
    if ratio >= 0.48:
        return "medium" if is_en else "moyen"
    if ratio >= 0.28:
        return "medium-low" if is_en else "moyen-bas"
    return "low" if is_en else "bas"


# ---------------------------------------------------------------------------
# Probability helpers
# ---------------------------------------------------------------------------

def _normalize_score_payload(raw_payload: Any) -> dict[str, float]:
    if not isinstance(raw_payload, dict):
        return {}
    result: dict[str, float] = {}
    for label, value in raw_payload.items():
        canonical = _normalize_emotion_breakdown_label(str(label))
        if not canonical:
            continue
        try:
            result[canonical] = max(0.0, float(value))
        except Exception:
            continue
    return result


def _normalize_prediction_scores(raw_scores: list[float]) -> list[float]:
    if not raw_scores:
        return []

    sanitized = [float(s) for s in raw_scores]
    total = sum(sanitized)

    if total > 0 and all(0.0 <= s <= 1.0 for s in sanitized) and total <= 1.0001:
        return sanitized

    try:
        import math

        max_s = max(sanitized)
        exps = [math.exp(s - max_s) for s in sanitized]
        exp_total = sum(exps)
        if exp_total > 0:
            return [s / exp_total for s in exps]
    except Exception:
        pass

    if total > 0:
        return [s / total for s in sanitized]

    uniform = 1.0 / len(sanitized)
    return [uniform] * len(sanitized)


def _normalize_probability_distribution(scores: dict[str, float]) -> dict[str, float]:
    filtered = {k: max(0.0, float(v)) for k, v in scores.items()}
    total = sum(filtered.values())
    if total <= 0:
        labels = tuple(filtered.keys()) or ("neutral",)
        uniform = 1.0 / len(labels)
        return {lbl: uniform for lbl in labels}
    return {k: v / total for k, v in filtered.items()}


def _probability_distribution_to_percentages(scores: dict[str, float]) -> dict[str, int]:
    normalized = _normalize_probability_distribution(scores)
    base = {k: int(v * 100) for k, v in normalized.items()}
    remainder = 100 - sum(base.values())

    if remainder > 0:
        ranked = sorted(
            normalized.items(),
            key=lambda item: (item[1] * 100) - base[item[0]],
            reverse=True,
        )
        for label, _ in ranked[:remainder]:
            base[label] += 1

    return base


def _distribution_distance(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 1.0
    return sum(abs(float(left) - float(right)) for left, right in zip(a, b))


def _sanitize_keras_archive_config(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized = {
            key: _sanitize_keras_archive_config(item)
            for key, item in value.items()
            if key != "quantization_config"
        }
        class_name = str(sanitized.get("class_name") or "")
        config_payload = sanitized.get("config")
        if isinstance(config_payload, dict):
            if class_name == "RandomShear":
                for factor_key in ("x_factor", "y_factor"):
                    factor_value = config_payload.get(factor_key)
                    if isinstance(factor_value, list) and len(factor_value) == 2:
                        low = max(0.0, min(1.0, abs(float(factor_value[0]))))
                        high = max(0.0, min(1.0, abs(float(factor_value[1]))))
                        config_payload[factor_key] = [min(low, high), max(low, high)]
                    elif isinstance(factor_value, (int, float)):
                        config_payload[factor_key] = max(0.0, min(1.0, abs(float(factor_value))))
            elif class_name == "BatchNormalization":
                config_payload.pop("renorm", None)
                config_payload.pop("renorm_clipping", None)
                config_payload.pop("renorm_momentum", None)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_keras_archive_config(item) for item in value]
    return value


def _clamp01(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return 0.0


def _normalize_face_box(raw_box: Any) -> dict[str, float] | None:
    if not isinstance(raw_box, dict):
        return None

    left = _clamp01(raw_box.get("left"))
    top = _clamp01(raw_box.get("top"))
    right = _clamp01(raw_box.get("right"))
    bottom = _clamp01(raw_box.get("bottom"))

    if right <= left or bottom <= top:
        return None

    return {
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom,
    }


def _normalize_pixel_box(
    left: float,
    top: float,
    right: float,
    bottom: float,
    *,
    image_width: int,
    image_height: int,
    min_size: int = 24,
) -> tuple[int, int, int, int] | None:
    left_px = int(max(0, min(image_width, round(left))))
    top_px = int(max(0, min(image_height, round(top))))
    right_px = int(max(0, min(image_width, round(right))))
    bottom_px = int(max(0, min(image_height, round(bottom))))

    if right_px - left_px < min_size or bottom_px - top_px < min_size:
        return None

    return left_px, top_px, right_px, bottom_px


def _resampling_lanczos() -> Any:
    try:
        from PIL import Image

        return Image.Resampling.LANCZOS
    except Exception:
        try:
            from PIL import Image

            return Image.LANCZOS
        except Exception:
            return None


def _prediction_margin(predictions: list[dict[str, Any]]) -> float:
    if not predictions:
        return 0.0
    try:
        top1 = float(predictions[0].get("score", 0.0) or 0.0)
    except Exception:
        top1 = 0.0
    try:
        top2 = float(predictions[1].get("score", 0.0) or 0.0) if len(predictions) > 1 else 0.0
    except Exception:
        top2 = 0.0
    return max(0.0, top1 - top2)


def _prediction_score_for_label(predictions: list[dict[str, Any]], label: str) -> float:
    target = str(label or "").strip().lower()
    if not target:
        return 0.0
    for item in predictions:
        if str(item.get("label", "")).strip().lower() != target:
            continue
        try:
            return max(0.0, float(item.get("score", 0.0) or 0.0))
        except Exception:
            return 0.0
    return 0.0


def _frame_hint_face_area(frame_hint: dict[str, Any] | None) -> float:
    face_box = _normalize_face_box((frame_hint or {}).get("face_box"))
    if face_box is None:
        return 0.0
    return max(0.0, (face_box["right"] - face_box["left"]) * (face_box["bottom"] - face_box["top"]))


def _frame_hint_quality(frame_hint: dict[str, Any] | None) -> float:
    payload = dict(frame_hint or {})
    score = 0.0

    if bool(payload.get("face_detected")):
        score += 0.25
    if int(payload.get("face_count", 0) or 0) == 1:
        score += 0.20
    if bool(payload.get("looking_forward")):
        score += 0.25
    if bool(payload.get("centered")):
        score += 0.15
    posture = str(payload.get("posture", "") or "").strip().lower()
    if posture == "stable":
        score += 0.05

    face_area = _frame_hint_face_area(payload)
    if face_area >= 0.12:
        score += 0.10
    elif face_area >= 0.08:
        score += 0.07
    elif face_area >= _MIN_REPORTABLE_FACE_AREA:
        score += 0.04

    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Provider-level aggregation
# ---------------------------------------------------------------------------

def _provider_sample_denominator(provider_payload: dict[str, Any]) -> float:
    weighted_samples = float(provider_payload.get("weighted_samples", 0.0) or 0.0)
    if weighted_samples > 0:
        return weighted_samples
    return float(max(1, int(provider_payload.get("samples", 0) or 0)))


def _average_provider_share(provider_payload: dict[str, Any], label: str) -> int:
    samples = _provider_sample_denominator(provider_payload)
    distribution_totals = dict(provider_payload.get("distribution_totals") or {})
    return _format_percent(float(distribution_totals.get(label, 0.0) or 0.0) / samples / 100.0)


def _average_provider_emotion_probability(provider_payload: dict[str, Any], label: str) -> float:
    samples = _provider_sample_denominator(provider_payload)
    raw_emotion_totals = dict(provider_payload.get("raw_emotion_totals") or {})
    average_pct = float(raw_emotion_totals.get(label, 0.0) or 0.0) / samples
    return max(0.0, average_pct / 100.0)


def _average_weighted_tension_share(provider_payload: dict[str, Any]) -> int:
    direct = _average_provider_share(provider_payload, "tension cues")
    tense = _average_provider_share(provider_payload, "tense")
    low_aff = _average_provider_share(provider_payload, "low affect")
    alert = _average_provider_share(provider_payload, "alert")
    weighted = direct + (tense * 0.75) + (low_aff * 0.45) + (alert * 0.35)
    return max(0, min(100, round(weighted)))


def _empty_provider_metric_summary() -> dict[str, Any]:
    return {
        "dominant_label": "",
        "neutral_pct": 0,
        "engaged_pct": 0,
        "tension_pct": 0,
        "samples": 0,
    }


def _build_provider_metric_summary(provider_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "dominant_label": _top_counter_label(dict(provider_payload.get("labels") or {})),
        "neutral_pct": _average_provider_share(provider_payload, "neutral"),
        "engaged_pct": _average_provider_share(provider_payload, "engaged"),
        "tension_pct": _average_weighted_tension_share(provider_payload),
        "samples": int(provider_payload.get("samples", 0) or 0),
    }


def _provider_display_name(provider_name: str, response_language: str) -> str:
    normalized = str(provider_name or "").strip().lower()
    if normalized == "custom":
        return "Custom model" if str(response_language).strip().lower() == "en" else "Modele personnalise"
    return normalized.title() or "Model"


# ---------------------------------------------------------------------------
# Emotion breakdown: faithful to the model
# ---------------------------------------------------------------------------

def _build_model_emotion_breakdown(providers: dict[str, Any]) -> dict[str, int]:
    """
    Main emotion truth = average model probabilities over valid samples.
    No behavior/posture/smile adjustment here.
    """
    emotion_totals: dict[str, float] = {}
    total_samples = 0.0

    for provider_payload in providers.values():
        provider_payload = dict(provider_payload or {})
        try:
            provider_samples = float(provider_payload.get("raw_emotion_samples", 0.0) or 0.0)
        except Exception:
            provider_samples = 0.0
        if provider_samples <= 0:
            provider_samples = _provider_sample_denominator(provider_payload)
        if provider_samples <= 0:
            continue

        raw_emotion_totals = dict(provider_payload.get("raw_emotion_totals") or {})
        if not raw_emotion_totals:
            metadata = dict(provider_payload.get("metadata") or {})
            if isinstance(metadata.get("raw_emotion"), dict):
                raw_emotion_totals = _normalize_score_payload(metadata.get("raw_emotion"))
                provider_samples = 1.0
            elif isinstance(metadata.get("raw_predictions"), list):
                recovered_totals: dict[str, float] = {}
                for item in metadata.get("raw_predictions") or []:
                    if not isinstance(item, dict):
                        continue
                    canonical = _normalize_emotion_breakdown_label(str(item.get("label", "")))
                    if not canonical:
                        continue
                    try:
                        score = float(item.get("score", 0.0) or 0.0)
                    except Exception:
                        score = 0.0
                    recovered_totals[canonical] = score * 100.0 if 0.0 <= score <= 1.0 else score
                raw_emotion_totals = recovered_totals
                provider_samples = 1.0
        if not raw_emotion_totals:
            continue

        for raw_label, total_score in raw_emotion_totals.items():
            canonical = _normalize_emotion_breakdown_label(str(raw_label))
            if not canonical:
                continue
            try:
                emotion_totals[canonical] = emotion_totals.get(canonical, 0.0) + float(total_score)
            except Exception:
                continue

        total_samples += provider_samples

    if total_samples <= 0 or not emotion_totals:
        return {}

    averaged_probs = {
        label: max(0.0, total_score / total_samples) / 100.0
        for label, total_score in emotion_totals.items()
    }

    return _probability_distribution_to_percentages(averaged_probs)


# ---------------------------------------------------------------------------
# Public observation update
# ---------------------------------------------------------------------------

def update_visual_observations(
    current: dict[str, Any] | None,
    *,
    mediapipe: dict[str, Any] | None,
    provider_results: list[EmotionAnalysis],
) -> dict[str, Any]:
    merged = empty_visual_observations()
    if isinstance(current, dict):
        merged.update(current)

    merged["sample_count"] = int(merged.get("sample_count", 0) or 0) + 1

    if isinstance(mediapipe, dict):
        if bool(mediapipe.get("face_detected")):
            merged["face_detected_count"] = int(merged.get("face_detected_count", 0) or 0) + 1
        if bool(mediapipe.get("centered")):
            merged["centered_count"] = int(merged.get("centered_count", 0) or 0) + 1
        if bool(mediapipe.get("looking_forward")):
            merged["looking_forward_count"] = int(merged.get("looking_forward_count", 0) or 0) + 1
        if int(mediapipe.get("face_count", 0) or 0) > 1:
            merged["multiple_faces_count"] = int(merged.get("multiple_faces_count", 0) or 0) + 1

        expression = str(mediapipe.get("expression", "") or "").strip().lower()
        if expression:
            expressions = Counter(merged.get("expressions") or {})
            expressions[expression] += 1
            merged["expressions"] = dict(expressions)
            if expression == "smiling":
                merged["smile_count"] = int(merged.get("smile_count", 0) or 0) + 1

        posture = str(mediapipe.get("posture", "") or "").strip().lower()
        if posture:
            postures = Counter(merged.get("postures") or {})
            postures[posture] += 1
            merged["postures"] = dict(postures)
            if posture == "stable":
                merged["stable_posture_count"] = int(merged.get("stable_posture_count", 0) or 0) + 1

        raw_objects = mediapipe.get("objects")
        if isinstance(raw_objects, list):
            object_counts = Counter(merged.get("object_counts") or {})
            confidence_totals = Counter(merged.get("object_confidence_totals") or {})
            object_seen = False
            for item in raw_objects:
                if not isinstance(item, dict):
                    continue
                label = str(item.get("label") or item.get("class") or item.get("name") or "").strip().lower()
                if not label or label == "person":
                    continue
                try:
                    score = float(item.get("score", item.get("confidence", item.get("probability", 0))) or 0)
                except Exception:
                    score = 0.0
                if 0.0 < score <= 1.0:
                    score *= 100.0
                object_counts[label] += 1
                confidence_totals[label] += max(0.0, min(100.0, score))
                object_seen = True
            if object_seen:
                merged["object_sample_count"] = int(merged.get("object_sample_count", 0) or 0) + 1
                merged["object_counts"] = dict(object_counts)
                merged["object_confidence_totals"] = dict(confidence_totals)

    providers_payload = _filter_active_providers(merged.get("providers") or {})
    active_names = _active_provider_names()

    for result in provider_results:
        provider_name = str(result.provider).strip().lower()
        if provider_name not in active_names:
            continue

        provider_state = dict(providers_payload.get(provider_name) or {})
        provider_state["ready"] = result.ready
        provider_state["summary"] = result.summary
        provider_state["last_label"] = _canonical_model_label(result.label)
        provider_state["last_confidence"] = result.confidence
        provider_state["attempts"] = int(provider_state.get("attempts", 0) or 0) + 1
        metadata = dict(result.metadata or {})
        is_reportable = bool(metadata.get("reportable", True))
        report_weight = max(0.0, float(metadata.get("report_weight", 1.0) or 0.0)) if is_reportable else 0.0

        if result.ready and is_reportable:
            provider_state["samples"] = int(provider_state.get("samples", 0) or 0) + 1
            provider_state["weighted_samples"] = float(provider_state.get("weighted_samples", 0.0) or 0.0) + report_weight

        # Separate interpretation labels for UI/business flags only
        label_counter = Counter(provider_state.get("labels") or {})
        soft_label = _soft_visual_label(result.label)
        if soft_label:
            label_counter[soft_label] += 1
            if soft_label == "engaged":
                provider_state["engaged_count"] = int(provider_state.get("engaged_count", 0) or 0) + 1
            if soft_label == "tension cues":
                provider_state["tension_count"] = int(provider_state.get("tension_count", 0) or 0) + 1
        provider_state["labels"] = dict(label_counter)

        provider_state["metadata"] = metadata

        raw_distribution: Any = {}
        if result.ready and isinstance(metadata, dict):
            if isinstance(metadata.get("raw_emotion"), dict):
                raw_distribution = metadata["raw_emotion"]
            elif isinstance(metadata.get("raw_predictions"), list):
                raw_distribution = metadata["raw_predictions"]

        distribution_totals = dict(provider_state.get("distribution_totals") or {})
        raw_emotion_totals = dict(provider_state.get("raw_emotion_totals") or {})
        raw_emotion_samples_added = 0.0
        raw_weight = report_weight if is_reportable and report_weight > 0 else 1.0

        if isinstance(raw_distribution, list):
            for item in raw_distribution:
                if not isinstance(item, dict):
                    continue

                raw_label = str(item.get("label", ""))
                canonical = _normalize_emotion_breakdown_label(raw_label)
                soft_label = _soft_visual_label(raw_label)

                try:
                    raw_score = float(item.get("score", 0.0) or 0.0)
                    score = (raw_score * 100.0 if 0.0 <= raw_score <= 1.0 else raw_score) * raw_weight
                except Exception:
                    score = 0.0

                if canonical:
                    raw_emotion_totals[canonical] = float(raw_emotion_totals.get(canonical, 0.0) or 0.0) + score
                if is_reportable and soft_label:
                    distribution_totals[soft_label] = float(distribution_totals.get(soft_label, 0.0) or 0.0) + score
            if raw_distribution:
                raw_emotion_samples_added = raw_weight

        else:
            normalized_scores = _normalize_score_payload(raw_distribution)
            for canonical, score in normalized_scores.items():
                weighted_score = score * raw_weight
                raw_emotion_totals[canonical] = float(raw_emotion_totals.get(canonical, 0.0) or 0.0) + weighted_score

                soft_label = _soft_visual_label(canonical)
                if is_reportable and soft_label:
                    distribution_totals[soft_label] = float(distribution_totals.get(soft_label, 0.0) or 0.0) + weighted_score
            if normalized_scores:
                raw_emotion_samples_added = raw_weight

        if distribution_totals:
            provider_state["distribution_totals"] = distribution_totals
        if raw_emotion_totals:
            provider_state["raw_emotion_totals"] = raw_emotion_totals
        if raw_emotion_samples_added > 0:
            provider_state["raw_emotion_samples"] = float(provider_state.get("raw_emotion_samples", 0.0) or 0.0) + raw_emotion_samples_added

        providers_payload[provider_name] = provider_state

    merged["providers"] = providers_payload
    return merged


# ---------------------------------------------------------------------------
# Public metric / flag / signal builders
# ---------------------------------------------------------------------------

def build_visual_metrics(
    observations: dict[str, Any] | None,
    response_language: str = "fr",
) -> dict[str, Any]:
    payload = observations if isinstance(observations, dict) else {}
    sample_count = int(payload.get("sample_count", 0) or 0)
    expressions = dict(payload.get("expressions") or {})
    postures = dict(payload.get("postures") or {})
    providers = _filter_active_providers(payload.get("providers") or {})
    object_counts = dict(payload.get("object_counts") or {})
    object_confidence_totals = dict(payload.get("object_confidence_totals") or {})
    object_sample_count = int(payload.get("object_sample_count", 0) or 0)
    top_objects = []
    for label, raw_count in sorted(object_counts.items(), key=lambda item: int(item[1] or 0), reverse=True)[:8]:
        count = int(raw_count or 0)
        confidence_total = float(object_confidence_totals.get(label, 0.0) or 0.0)
        top_objects.append({
            "label": str(label),
            "count": count,
            "avg_confidence": round(confidence_total / max(count, 1)),
        })

    face_ratio = _safe_ratio(int(payload.get("face_detected_count", 0) or 0), sample_count)
    centered_ratio = _safe_ratio(int(payload.get("centered_count", 0) or 0), sample_count)
    looking_forward_ratio = _safe_ratio(int(payload.get("looking_forward_count", 0) or 0), sample_count)
    multiple_faces_ratio = _safe_ratio(int(payload.get("multiple_faces_count", 0) or 0), sample_count)
    stable_posture_ratio = _safe_ratio(int(payload.get("stable_posture_count", 0) or 0), sample_count)
    smile_ratio = _safe_ratio(int(payload.get("smile_count", 0) or 0), sample_count)
    neutral_ratio = _safe_ratio(int(expressions.get("neutral", 0) or 0), sample_count)
    engaged_ratio = _safe_ratio(int(expressions.get("smiling", 0) or 0), sample_count)

    visual_enthusiasm_ratio = (
        (looking_forward_ratio * 0.35) +
        (centered_ratio * 0.20) +
        (smile_ratio * 0.45)
    )

    provider_summaries = {
        name: _build_provider_metric_summary(dict(payload_ or {}))
        for name, payload_ in providers.items()
    }

    model_emotion_breakdown = _build_model_emotion_breakdown(providers)
    dominant_emotion = _top_counter_label(model_emotion_breakdown) if model_emotion_breakdown else ""
    dominant_emotion_pct = int(model_emotion_breakdown.get(dominant_emotion, 0) or 0) if dominant_emotion else 0

    is_en = str(response_language).strip().lower() == "en"
    if sample_count <= 3:
        confidence_note = (
            "Low confidence: too few visual samples were captured."
            if is_en else
            "Confiance faible : trop peu d'echantillons visuels ont ete captures."
        )
    elif face_ratio < 0.5 or multiple_faces_ratio > 0.2:
        confidence_note = (
            "Moderate confidence: visual cues should remain secondary because capture quality was uneven."
            if is_en else
            "Confiance moyenne : les indices visuels doivent rester secondaires car la capture a ete inegale."
        )
    else:
        confidence_note = (
            "High confidence: visual capture stayed stable for most of the interview."
            if is_en else
            "Confiance elevee : la capture visuelle est restee stable pendant la majeure partie de l'entretien."
        )

    return {
        # Generic visual metrics
        "sample_count": sample_count,
        "face_detected_pct": _format_percent(face_ratio),
        "centered_pct": _format_percent(centered_ratio),
        "looking_forward_pct": _format_percent(looking_forward_ratio),
        "multiple_faces_pct": _format_percent(multiple_faces_ratio),
        "stable_posture_pct": _format_percent(stable_posture_ratio),
        "smile_pct": _format_percent(smile_ratio),
        "neutral_pct": _format_percent(neutral_ratio),
        "engaged_pct": _format_percent(engaged_ratio),
        "smile_count": int(payload.get("smile_count", 0) or 0),
        "dominant_expression": _top_counter_label(expressions),
        "dominant_posture": _top_counter_label(postures),
        "visual_enthusiasm_pct": _format_percent(visual_enthusiasm_ratio),
        "visual_enthusiasm_bucket": _bucket_visual_enthusiasm(visual_enthusiasm_ratio, response_language),
        "object_sample_count": object_sample_count,
        "object_counts": object_counts,
        "detected_objects": top_objects,
        "detected_object_total": sum(int(value or 0) for value in object_counts.values()),

        # Model-faithful emotion output
        "model_emotion_breakdown": model_emotion_breakdown,
        "dominant_emotion": dominant_emotion,
        "dominant_emotion_pct": dominant_emotion_pct,
        "model_emotion_breakdown_available": bool(model_emotion_breakdown),
        # Backward-compatible aliases still consumed by report / insights UIs.
        "emotion_breakdown": dict(model_emotion_breakdown),
        "emotion_breakdown_available": bool(model_emotion_breakdown),
        "raw_emotion_breakdown": dict(model_emotion_breakdown),
        "raw_emotion_breakdown_available": bool(model_emotion_breakdown),

        # Business-facing interpretation summaries
        "provider_metrics": provider_summaries,
        "custom": provider_summaries.get("custom", _empty_provider_metric_summary()),

        "confidence_note": confidence_note,
    }


def build_visual_flags(
    observations: dict[str, Any] | None,
    response_language: str = "fr",
) -> list[str]:
    metrics = build_visual_metrics(observations, response_language)
    flags: list[str] = []

    if metrics["sample_count"] <= 3:
        return ["analyse_visuelle_insuffisante"]

    if metrics["neutral_pct"] >= 88 and metrics["smile_pct"] < 10:
        flags.append("faible_expressivite")
    if metrics["looking_forward_pct"] < 45 or metrics["centered_pct"] < 45:
        flags.append("engagement_visuel_irregulier")
    if metrics["multiple_faces_pct"] > 20:
        flags.append("analyse_visuelle_peu_fiable")

    strongest_tension_pct = max(
        [0] + [
            int(dict(pm).get("tension_pct", 0) or 0)
            for pm in dict(metrics.get("provider_metrics") or {}).values()
        ]
    )
    if strongest_tension_pct >= 28:
        flags.append("tension_apparente_moderee")
    elif strongest_tension_pct >= 16:
        flags.append("tension_apparente_legere")

    if metrics["smile_pct"] >= 25 and metrics["visual_enthusiasm_pct"] >= 48:
        flags.append("expressivite_positive")
    if metrics["visual_enthusiasm_pct"] >= 66 and metrics["smile_pct"] >= 18:
        flags.append("enthousiasme_visuel_positif")
    elif metrics["visual_enthusiasm_pct"] >= 42:
        flags.append("enthousiasme_visuel_mesure")
    if metrics["stable_posture_pct"] >= 70 and metrics["face_detected_pct"] >= 75:
        flags.append("presence_professionnelle_stable")
    if metrics["neutral_pct"] >= 88 and metrics["visual_enthusiasm_pct"] < 48:
        flags.append("sobriete_visuelle_mais_motivation_a_croiser")

    return flags


def build_visual_signals(
    observations: dict[str, Any] | None,
    response_language: str = "fr",
) -> list[str]:
    metrics = build_visual_metrics(observations, response_language)
    flags = build_visual_flags(observations, response_language)
    is_en = str(response_language).strip().lower() == "en"

    if metrics["sample_count"] <= 3:
        return [
            "Visual analysis remains limited because too few frames were captured."
            if is_en else
            "L'analyse visuelle reste limitee car trop peu d'images ont ete capturees."
        ]

    signals: list[str] = []

    if metrics["face_detected_pct"] >= 75:
        signals.append(
            "Visual presence remained stable and well framed for most of the interview."
            if is_en else
            "La presence visuelle est restee stable et bien cadree durant la majeure partie de l'entretien."
        )
    elif metrics["face_detected_pct"] >= 50:
        signals.append(
            "Visual presence was globally stable."
            if is_en else
            "La presence visuelle a ete globalement stable."
        )

    if metrics["looking_forward_pct"] >= 68 and metrics["centered_pct"] >= 65:
        signals.append(
            "Visual engagement appeared consistent on screen."
            if is_en else
            "L'engagement visuel a semble globalement constant a l'ecran."
        )
    elif "engagement_visuel_irregulier" in flags:
        signals.append(
            "Visual attention appeared uneven at times."
            if is_en else
            "L'attention visuelle a paru inegale par moments."
        )

    if "presence_professionnelle_stable" in flags:
        signals.append(
            "The candidate maintained a stable and professional visual posture."
            if is_en else
            "Le candidat a maintenu une posture visuelle stable et professionnelle."
        )

    if metrics["neutral_pct"] >= 88:
        expressiveness = "rather low" if metrics["smile_pct"] < 10 else "moderate"
        expressiveness_fr = "plutot faible" if metrics["smile_pct"] < 10 else "moderee"
        signals.append(
            f"Facial expression remained mostly neutral ({metrics['neutral_pct']}%), suggesting composed emotional control with {expressiveness} expressiveness."
            if is_en else
            f"L'expression faciale est restee majoritairement neutre ({metrics['neutral_pct']} %), ce qui suggere une bonne maitrise emotionnelle avec une expressivite {expressiveness_fr}."
        )
    elif metrics["smile_pct"] >= 25:
        signals.append(
            "Facial expression showed several positive and open moments."
            if is_en else
            "L'expression faciale a montre plusieurs moments positifs et ouverts."
        )

    # Faithful model output mentioned separately
    if metrics["dominant_emotion"]:
        signals.append(
            f"Dominant model emotion: {metrics['dominant_emotion']} ({metrics['dominant_emotion_pct']}%)."
            if is_en else
            f"Emotion dominante du modele : {metrics['dominant_emotion']} ({metrics['dominant_emotion_pct']} %)."
        )

    detected_objects = list(metrics.get("detected_objects") or [])
    if detected_objects:
        object_labels = ", ".join(str(item.get("label") or "") for item in detected_objects[:3] if isinstance(item, dict) and item.get("label"))
        if object_labels:
            signals.append(
                f"Objects detected during the interview: {object_labels}."
                if is_en else
                f"Objets detectes pendant l'entretien : {object_labels}."
            )

    signals.append(
        f"Visual enthusiasm score: {metrics['visual_enthusiasm_bucket']}."
        if is_en else
        f"Score d'enthousiasme visuel : {metrics['visual_enthusiasm_bucket']}."
    )

    if metrics["smile_count"] >= 3:
        signals.append(
            f"{metrics['smile_count']} smile moments were detected."
            if is_en else
            f"{metrics['smile_count']} moments de sourire ont ete detectes."
        )

    provider_metrics_map = dict(metrics.get("provider_metrics") or {})
    ordered_names = ["custom"] + [n for n in provider_metrics_map if n != "custom"]
    for provider_name in ordered_names:
        pm = dict(provider_metrics_map.get(provider_name) or {})
        dominant = str(pm.get("dominant_label", "") or "").strip()
        if not dominant:
            continue
        pretty = _provider_display_name(provider_name, response_language)

        if dominant == "neutral":
            signals.append(
                f"{pretty} observed mostly neutral facial cues ({pm['neutral_pct']}% neutral)."
                if is_en else
                f"{pretty} a observe des indices faciaux majoritairement neutres ({pm['neutral_pct']} % neutre)."
            )
        elif dominant == "engaged":
            signals.append(
                f"{pretty} detected engaged expressions several times."
                if is_en else
                f"{pretty} a detecte des expressions engagees a plusieurs reprises."
            )
        elif dominant == "tension cues":
            signals.append(
                f"{pretty} detected occasional apparent tension cues ({pm['tension_pct']}%)."
                if is_en else
                f"{pretty} a detecte quelques signes apparents de tension ({pm['tension_pct']} %)."
            )

    if "enthousiasme_visuel_positif" in flags:
        signals.append(
            "Visual enthusiasm appeared clearly positive at several moments."
            if is_en else
            "L'enthousiasme visuel a paru nettement positif a plusieurs moments."
        )
    elif "enthousiasme_visuel_mesure" in flags:
        signals.append(
            "Visual enthusiasm remained present but measured."
            if is_en else
            "L'enthousiasme visuel est reste present mais mesure."
        )

    if "tension_apparente_moderee" in flags:
        signals.append(
            "Moderate apparent tension cues were observed and should remain secondary."
            if is_en else
            "Des signes apparents de tension moderes ont ete observes et doivent rester secondaires."
        )
    elif "tension_apparente_legere" in flags:
        signals.append(
            "Light apparent tension cues appeared occasionally."
            if is_en else
            "De legers signes apparents de tension sont apparus ponctuellement."
        )

    seen: set[str] = set()
    deduped: list[str] = []
    for signal in signals:
        if signal not in seen:
            deduped.append(signal)
            seen.add(signal)

    return deduped[:6]


def build_visual_llm_context(
    observations: dict[str, Any] | None,
    response_language: str = "fr",
) -> dict[str, Any]:
    metrics = build_visual_metrics(observations, response_language)
    return {
        "metrics": metrics,
        "signals": build_visual_signals(observations, response_language),
        "heuristic_flags": build_visual_flags(observations, response_language),
        "confidence_note": metrics["confidence_note"],
    }


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def emotion_analysis_to_dict(result: EmotionAnalysis) -> dict[str, Any]:
    return asdict(result)


# ---------------------------------------------------------------------------
# Analyzer implementations
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class NoopEmotionAnalyzer:
    provider: str = "none"

    def describe(self) -> EmotionAnalysis:
        return EmotionAnalysis(
            provider=self.provider,
            ready=False,
            summary="Backend emotion analysis is disabled. MediaPipe remains the active live analysis layer in the frontend.",
        )

    def analyze_image_bytes(
        self,
        raw_bytes: bytes,
        *,
        frame_hint: dict[str, Any] | None = None,
    ) -> EmotionAnalysis:
        return self.describe()


@dataclass(slots=True)
class CustomEmotionAnalyzer:
    model_dir: Path | None
    provider: str = "custom"
    _labels: list[str] = field(default_factory=list, init=False, repr=False)
    _input_shape: tuple[int, int, int] = field(default=(224, 224, 3), init=False, repr=False)
    _predict_fn: Any = field(default=None, init=False, repr=False)
    _keras_model: Any = field(default=None, init=False, repr=False)
    _keras_runtime: str | None = field(default=None, init=False, repr=False)
    _input_name: str | None = field(default=None, init=False, repr=False)
    _sanitized_keras_path: Path | None = field(default=None, init=False, repr=False)
    _mtcnn_detector: Any = field(default=None, init=False, repr=False)
    _validation_checked: bool = field(default=False, init=False, repr=False)
    _validation_error: str | None = field(default=None, init=False, repr=False)
    _validation_metadata: dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    # --- Path helpers ---

    def _model_root(self) -> Path | None:
        if self.model_dir is None:
            return None
        candidate = Path(self.model_dir)
        return candidate.parent if candidate.name == "saved_model" else candidate

    def _saved_model_dir(self) -> Path | None:
        root = self._model_root()
        if root is None:
            return None

        direct = root / "saved_model"
        if direct.exists():
            return direct
        if (root / "saved_model.pb").exists():
            return root
        return direct

    def _keras_model_path(self) -> Path | None:
        root = self._model_root()
        if root is None:
            return None
        candidate = root / "model.keras"
        return candidate if candidate.exists() else None

    def _prepare_keras_compat_modules(self) -> None:
        module_alias_pairs = (
            ("keras.src.models.functional", "tf_keras.src.models.functional"),
            ("keras.src.models.sequential", "tf_keras.src.models.sequential"),
            ("keras.src.models.model", "tf_keras.src.models.model"),
            ("keras.src.engine.functional", "tf_keras.src.engine.functional"),
            ("keras.src.engine.sequential", "tf_keras.src.engine.sequential"),
            ("keras.src.engine.training", "tf_keras.src.engine.training"),
        )

        for left_name, right_name in module_alias_pairs:
            left_module = sys.modules.get(left_name)
            right_module = sys.modules.get(right_name)

            if left_module is None:
                try:
                    left_module = importlib.import_module(left_name)
                except Exception:
                    left_module = None

            if right_module is None:
                try:
                    right_module = importlib.import_module(right_name)
                except Exception:
                    right_module = None

            if left_module is not None and right_module is None:
                sys.modules.setdefault(right_name, left_module)
            elif right_module is not None and left_module is None:
                sys.modules.setdefault(left_name, right_module)

    def _sanitize_keras_archive(self, keras_model_path: Path) -> Path:
        fd, temp_path = tempfile.mkstemp(suffix=".keras")
        os.close(fd)
        temp_model_path = Path(temp_path)

        try:
            with ZipFile(keras_model_path) as archive_in, ZipFile(temp_model_path, "w", compression=ZIP_DEFLATED) as archive_out:
                for member_name in archive_in.namelist():
                    payload = archive_in.read(member_name)
                    if member_name == "config.json":
                        config_payload = json.loads(payload.decode("utf-8"))
                        config_payload = _sanitize_keras_archive_config(config_payload)
                        payload = json.dumps(config_payload).encode("utf-8")
                    archive_out.writestr(member_name, payload)
        except Exception:
            temp_model_path.unlink(missing_ok=True)
            raise

        return temp_model_path

    def _labels_path(self) -> Path | None:
        root = self._model_root()
        return (root / "labels.json") if root is not None else None

    def _metadata_path(self) -> Path | None:
        root = self._model_root()
        return (root / "metadata.json") if root is not None else None

    # --- Lazy loading ---

    def _ensure_assets_loaded(self) -> None:
        if self._labels:
            return

        labels_path = self._labels_path()
        metadata_path = self._metadata_path()

        if labels_path is None or not labels_path.exists():
            raise FileNotFoundError("labels.json is missing for the custom emotion model.")

        with labels_path.open("r", encoding="utf-8") as fh:
            labels_payload = json.load(fh)

        if not isinstance(labels_payload, list) or not labels_payload:
            raise ValueError("labels.json must contain a non-empty list of class labels.")

        self._labels = [
            _canonical_model_label(str(lbl).strip())
            for lbl in labels_payload
            if str(lbl).strip()
        ]
        if not self._labels:
            raise ValueError("No valid class label was found in labels.json.")

        if metadata_path is not None and metadata_path.exists():
            with metadata_path.open("r", encoding="utf-8") as fh:
                meta = json.load(fh)

            input_shape = meta.get("input_shape")
            if (
                isinstance(input_shape, list)
                and len(input_shape) >= 3
                and all(isinstance(v, (int, float)) for v in input_shape[:3])
            ):
                self._input_shape = tuple(int(v) for v in input_shape[:3])  # type: ignore[assignment]

    def _load_predict_fn(self) -> Any:
        if self._predict_fn is not None:
            return self._predict_fn

        if find_spec("tensorflow") is None or find_spec("PIL") is None:
            raise ModuleNotFoundError("tensorflow/Pillow")

        import tensorflow as tf

        def _load_saved_model_predict_fn() -> Any:
            saved_model_dir = self._saved_model_dir()
            if saved_model_dir is None or not saved_model_dir.exists():
                raise FileNotFoundError(
                    "Neither model.keras nor SavedModel directory is available for the custom emotion model."
                )

            model = tf.saved_model.load(str(saved_model_dir))
            signatures = getattr(model, "signatures", {}) or {}
            predict_fn = signatures.get("serving_default") or signatures.get("serve")
            if predict_fn is None:
                raise ValueError("The custom SavedModel does not expose a usable serving signature.")

            _, input_sig = predict_fn.structured_input_signature
            self._keras_model = None
            self._keras_runtime = "tf.saved_model"
            self._input_name = next(iter(input_sig.keys())) if input_sig else None
            self._predict_fn = predict_fn
            return self._predict_fn

        keras_model_path = self._keras_model_path()
        load_errors: list[str] = []
        if keras_model_path is not None:
            self._prepare_keras_compat_modules()
            sanitized_model_path: Path | None = None
            try:
                sanitized_model_path = self._sanitize_keras_archive(keras_model_path)
                keras_model_uri = str(sanitized_model_path)

                if find_spec("keras") is not None:
                    try:
                        import keras

                        self._keras_model = keras.models.load_model(keras_model_uri, compile=False)
                        self._keras_runtime = "keras"
                    except Exception as exc:
                        load_errors.append(f"keras: {exc}")

                if self._keras_model is None:
                    try:
                        self._keras_model = tf.keras.models.load_model(keras_model_uri, compile=False)
                        self._keras_runtime = "tf.keras"
                    except Exception as exc:
                        load_errors.append(f"tf.keras: {exc}")

                if self._keras_model is None and find_spec("tf_keras") is not None:
                    try:
                        import tf_keras

                        self._keras_model = tf_keras.models.load_model(keras_model_uri, compile=False)
                        self._keras_runtime = "tf_keras"
                    except Exception as exc:
                        load_errors.append(f"tf_keras: {exc}")
            except Exception as exc:
                load_errors.append(f"model.keras preparation: {exc}")
            finally:
                if sanitized_model_path is not None:
                    try:
                        sanitized_model_path.unlink(missing_ok=True)
                    except Exception:
                        pass

            if self._keras_model is not None:
                self._input_name = None
                self._predict_fn = self._keras_model
                return self._predict_fn

        saved_model_dir = self._saved_model_dir()
        if saved_model_dir is not None and saved_model_dir.exists():
            try:
                return _load_saved_model_predict_fn()
            except Exception as exc:
                load_errors.append(f"saved_model: {exc}")

        if keras_model_path is not None or load_errors:
            details = "\n".join(load_errors) if load_errors else "No compatible Keras loader is available."
            raise RuntimeError(f"Unable to load the custom emotion model.\n{details}")

        raise FileNotFoundError("Neither model.keras nor SavedModel directory is available for the custom emotion model.")

    def _predict_scores_from_batch(self, input_batch: Any) -> list[float]:
        import numpy as np
        import tensorflow as tf

        predict_fn = self._load_predict_fn()
        tensor_batch = tf.convert_to_tensor(input_batch)

        if self._keras_model is not None:
            outputs = predict_fn(tensor_batch, training=False)
            raw_scores = np.asarray(outputs).astype("float32").reshape(-1).tolist()
        else:
            if self._input_name:
                outputs = predict_fn(**{self._input_name: tensor_batch})
            else:
                outputs = predict_fn(tensor_batch)
            first_output = next(iter(outputs.values()))
            raw_scores = np.asarray(first_output).astype("float32").reshape(-1).tolist()

        normalized_scores = _normalize_prediction_scores(raw_scores)
        if len(normalized_scores) != len(self._labels):
            raise ValueError("The custom model output size does not match labels.json.")
        return normalized_scores

    def _validate_model_behavior(self) -> None:
        if self._validation_checked:
            return

        self._validation_checked = True
        self._validation_error = None
        self._validation_metadata = {}

        try:
            import numpy as np

            height = max(1, int(self._input_shape[0] or 224))
            width = max(1, int(self._input_shape[1] or 224))
            rng = np.random.default_rng(_MODEL_PROBE_NOISE_SEED)

            probes = {
                "black": np.zeros((1, height, width, 3), dtype="float32"),
                "white": np.ones((1, height, width, 3), dtype="float32") * 255.0,
                "noise": rng.uniform(0, 255, size=(1, height, width, 3)).astype("float32"),
            }
            predictions = {
                probe_name: self._predict_scores_from_batch(batch)
                for probe_name, batch in probes.items()
            }

            distances = {
                "black_vs_white": _distribution_distance(predictions["black"], predictions["white"]),
                "black_vs_noise": _distribution_distance(predictions["black"], predictions["noise"]),
                "white_vs_noise": _distribution_distance(predictions["white"], predictions["noise"]),
            }
            max_distance = max(distances.values(), default=0.0)

            self._validation_metadata = {
                "probe_distances": {key: round(value, 6) for key, value in distances.items()},
                "max_probe_distance": round(max_distance, 6),
            }

            if max_distance < _MODEL_PROBE_VARIATION_MIN:
                self._validation_error = (
                    "The exported model appears input-invariant: black/white/noise probes produce nearly identical outputs."
                )
        except Exception as exc:
            self._validation_error = f"Model validation failed: {exc}"

    def _square_crop_spec(
        self,
        face_box: dict[str, float],
        *,
        image_width: int,
        image_height: int,
        pad_x: float,
        pad_top: float,
        pad_bottom: float,
    ) -> dict[str, float] | None:
        box_width_px = (face_box["right"] - face_box["left"]) * image_width
        box_height_px = (face_box["bottom"] - face_box["top"]) * image_height
        left_px = (face_box["left"] * image_width) - (box_width_px * pad_x)
        right_px = (face_box["right"] * image_width) + (box_width_px * pad_x)
        top_px = (face_box["top"] * image_height) - (box_height_px * pad_top)
        bottom_px = (face_box["bottom"] * image_height) + (box_height_px * pad_bottom)

        padded_width_px = max(1.0, right_px - left_px)
        padded_height_px = max(1.0, bottom_px - top_px)
        square_side_px = max(padded_width_px, padded_height_px)
        center_x_px = (left_px + right_px) / 2.0
        center_y_px = (top_px + bottom_px) / 2.0

        if square_side_px < 24:
            return None

        return {
            "center_x": float(center_x_px),
            "center_y": float(center_y_px),
            "side": float(square_side_px),
        }

    def _square_face_crop_spec(
        self,
        face_box: dict[str, float],
        *,
        image_width: int,
        image_height: int,
    ) -> dict[str, float] | None:
        return self._square_crop_spec(
            face_box,
            image_width=image_width,
            image_height=image_height,
            pad_x=_FACE_CROP_PAD_X,
            pad_top=_FACE_CROP_PAD_TOP,
            pad_bottom=_FACE_CROP_PAD_BOTTOM,
        )

    def _square_face_redetect_spec(
        self,
        face_box: dict[str, float],
        *,
        image_width: int,
        image_height: int,
    ) -> dict[str, float] | None:
        return self._square_crop_spec(
            face_box,
            image_width=image_width,
            image_height=image_height,
            pad_x=_FACE_REDETECT_PAD_X,
            pad_top=_FACE_REDETECT_PAD_TOP,
            pad_bottom=_FACE_REDETECT_PAD_BOTTOM,
        )

    def _crop_centered_square(
        self,
        image: Any,
        *,
        center_x_px: float,
        center_y_px: float,
        side_px: float,
    ) -> tuple[Any, dict[str, Any]] | None:
        import numpy as np
        from PIL import Image

        width, height = image.size
        side = max(24, int(round(float(side_px))))
        half_side = side / 2.0

        desired_left = int(round(float(center_x_px) - half_side))
        desired_top = int(round(float(center_y_px) - half_side))
        desired_right = desired_left + side
        desired_bottom = desired_top + side

        pad_left = max(0, -desired_left)
        pad_top = max(0, -desired_top)
        pad_right = max(0, desired_right - width)
        pad_bottom = max(0, desired_bottom - height)

        if pad_left or pad_top or pad_right or pad_bottom:
            padded_array = np.pad(
                np.asarray(image, dtype="uint8"),
                ((pad_top, pad_bottom), (pad_left, pad_right), (0, 0)),
                mode="edge",
            )
            working_image = Image.fromarray(padded_array, mode="RGB")
        else:
            working_image = image

        crop_left = desired_left + pad_left
        crop_top = desired_top + pad_top
        crop_right = desired_right + pad_left
        crop_bottom = desired_bottom + pad_top

        crop_box = _normalize_pixel_box(
            crop_left,
            crop_top,
            crop_right,
            crop_bottom,
            image_width=working_image.size[0],
            image_height=working_image.size[1],
        )
        if crop_box is None:
            return None

        original_pixel_box = [
            int(max(0, desired_left)),
            int(max(0, desired_top)),
            int(min(width, desired_right)),
            int(min(height, desired_bottom)),
        ]

        return (
            working_image.crop(crop_box),
            {
                "pixel_box": [int(crop_box[0]), int(crop_box[1]), int(crop_box[2]), int(crop_box[3])],
                "original_pixel_box": original_pixel_box,
                "padding": {
                    "left": int(pad_left),
                    "top": int(pad_top),
                    "right": int(pad_right),
                    "bottom": int(pad_bottom),
                },
                "square_side": int(side),
            },
        )

    def _score_detected_face(
        self,
        face_rect: Any,
        *,
        image_width: int,
        image_height: int,
    ) -> float:
        x, y, w, h = (int(face_rect[0]), int(face_rect[1]), int(face_rect[2]), int(face_rect[3]))
        area = max(1.0, float(w * h))
        center_x = x + (w / 2.0)
        center_y = y + (h / 2.0)
        x_penalty = abs(center_x - (image_width / 2.0)) / max(1.0, image_width / 2.0)
        y_penalty = abs(center_y - (image_height * 0.35)) / max(1.0, image_height / 2.0)
        position_weight = max(0.35, 1.15 - (x_penalty * 0.55) - (y_penalty * 0.85))
        return area * position_weight

    def _load_mtcnn_detector(self) -> Any:
        if self._mtcnn_detector is not None:
            return self._mtcnn_detector
        if find_spec("mtcnn") is None:
            return None

        from mtcnn import MTCNN

        self._mtcnn_detector = MTCNN()
        return self._mtcnn_detector

    def _detect_face_box_with_mtcnn(self, image: Any) -> tuple[dict[str, float] | None, dict[str, Any]]:
        width, height = image.size

        try:
            import numpy as np

            detector = self._load_mtcnn_detector()
            if detector is None:
                return None, {"detector": "mtcnn-unavailable"}

            rgb_image = np.asarray(image, dtype="uint8")
            faces = detector.detect_faces(rgb_image) or []
            if not faces:
                return None, {"detector": "mtcnn", "detected_faces": 0}

            def _mtcnn_score(face_payload: dict[str, Any]) -> float:
                box = face_payload.get("box") or [0, 0, 0, 0]
                confidence = max(0.0, float(face_payload.get("confidence", 0.0) or 0.0))
                return self._score_detected_face(
                    box,
                    image_width=width,
                    image_height=height,
                ) * max(0.25, confidence)

            best_face = max(faces, key=_mtcnn_score)
            x, y, w, h = [int(value) for value in (best_face.get("box") or [0, 0, 0, 0])]
            pixel_box = _normalize_pixel_box(
                x,
                y,
                x + w,
                y + h,
                image_width=width,
                image_height=height,
            )
            if pixel_box is None:
                return None, {"detector": "mtcnn", "detected_faces": len(faces)}

            left_px, top_px, right_px, bottom_px = pixel_box
            normalized_face_box = _normalize_face_box(
                {
                    "left": left_px / width,
                    "top": top_px / height,
                    "right": right_px / width,
                    "bottom": bottom_px / height,
                }
            )
            if normalized_face_box is None:
                return None, {"detector": "mtcnn", "detected_faces": len(faces)}

            return normalized_face_box, {
                "detector": "mtcnn",
                "detected_faces": len(faces),
                "selected_face_box": [left_px, top_px, right_px, bottom_px],
                "selected_face_confidence": round(float(best_face.get("confidence", 0.0) or 0.0), 6),
                "keypoints": {
                    str(name): [int(point[0]), int(point[1])] if isinstance(point, (list, tuple)) and len(point) >= 2 else int(point)
                    for name, point in dict(best_face.get("keypoints") or {}).items()
                },
            }
        except Exception as exc:
            return None, {
                "detector": "mtcnn-error",
                "reason": str(exc),
            }

    def _detect_face_box_with_opencv(self, image: Any) -> tuple[dict[str, float] | None, dict[str, Any]]:
        width, height = image.size

        if find_spec("cv2") is None:
            return None, {"detector": "opencv-unavailable"}

        try:
            import cv2
            import numpy as np

            cascade_root = Path(getattr(cv2.data, "haarcascades", ""))
            cascade_names = (
                "haarcascade_frontalface_default.xml",
                "haarcascade_frontalface_alt.xml",
                "haarcascade_frontalface_alt2.xml",
                "haarcascade_profileface.xml",
            )
            classifiers: list[tuple[str, Any]] = []
            for cascade_name in cascade_names:
                cascade_path = cascade_root / cascade_name
                if not cascade_path.exists():
                    continue
                classifier = cv2.CascadeClassifier(str(cascade_path))
                if not classifier.empty():
                    classifiers.append((cascade_name, classifier))
            if not classifiers:
                return None, {"detector": "opencv-haarcascade-missing"}

            rgb_image = np.asarray(image, dtype="uint8")
            gray_base = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2GRAY)
            gray_equalized = cv2.equalizeHist(gray_base)
            min_face = max(24, int(round(min(width, height) * 0.12)))

            candidates: list[tuple[str, tuple[int, int, int, int]]] = []
            variants = [
                ("gray", gray_base, False),
                ("gray-equalized", gray_equalized, False),
                ("gray-flipped", cv2.flip(gray_base, 1), True),
                ("gray-equalized-flipped", cv2.flip(gray_equalized, 1), True),
            ]

            for cascade_name, classifier in classifiers:
                for variant_name, variant_image, is_flipped in variants:
                    for scale_factor, min_neighbors in ((1.08, 5), (1.05, 4)):
                        faces = classifier.detectMultiScale(
                            variant_image,
                            scaleFactor=scale_factor,
                            minNeighbors=min_neighbors,
                            minSize=(min_face, min_face),
                        )
                        for face in faces:
                            x, y, w, h = [int(value) for value in face]
                            if is_flipped:
                                x = width - x - w
                            candidates.append((f"{cascade_name}:{variant_name}", (x, y, w, h)))

            if not candidates:
                return None, {"detector": "opencv-haarcascade", "detected_faces": 0}

            best_source, best_face = max(
                candidates,
                key=lambda item: self._score_detected_face(
                    item[1],
                    image_width=width,
                    image_height=height,
                ),
            )
            x, y, w, h = best_face
            normalized_face_box = _normalize_face_box(
                {
                    "left": x / width,
                    "top": y / height,
                    "right": (x + w) / width,
                    "bottom": (y + h) / height,
                }
            )
            if normalized_face_box is None:
                return None, {"detector": "opencv-haarcascade", "detected_faces": len(candidates)}

            return normalized_face_box, {
                "detector": "opencv-haarcascade",
                "detected_faces": len(candidates),
                "selected_face_box": [x, y, x + w, y + h],
                "selected_detector_variant": best_source,
            }
        except Exception as exc:
            return None, {
                "detector": "opencv-haarcascade-error",
                "reason": str(exc),
            }

    def _detect_face_box(self, image: Any) -> tuple[dict[str, float] | None, dict[str, Any]]:
        backends = (
            self._detect_face_box_with_mtcnn,
            self._detect_face_box_with_opencv,
        )

        diagnostics: list[dict[str, Any]] = []
        for detector in backends:
            face_box, detector_meta = detector(image)
            if face_box is not None:
                detector_meta = dict(detector_meta or {})
                if diagnostics:
                    detector_meta["fallback_attempts"] = diagnostics
                return face_box, detector_meta
            if detector_meta:
                diagnostics.append(dict(detector_meta))

        return None, {
            "detector": "no-face-detected",
            "attempts": diagnostics,
        }

    def _map_face_box_from_crop(
        self,
        local_face_box: dict[str, float],
        *,
        crop_payload: dict[str, Any],
        image_width: int,
        image_height: int,
    ) -> dict[str, float] | None:
        square_side = max(1.0, float(crop_payload.get("square_side", 0) or 0))
        original_pixel_box = list(crop_payload.get("original_pixel_box") or [])
        padding = dict(crop_payload.get("padding") or {})
        if len(original_pixel_box) != 4:
            return None

        desired_left = float(original_pixel_box[0]) - float(padding.get("left", 0) or 0)
        desired_top = float(original_pixel_box[1]) - float(padding.get("top", 0) or 0)

        mapped = _normalize_face_box(
            {
                "left": (desired_left + (local_face_box["left"] * square_side)) / max(1.0, float(image_width)),
                "top": (desired_top + (local_face_box["top"] * square_side)) / max(1.0, float(image_height)),
                "right": (desired_left + (local_face_box["right"] * square_side)) / max(1.0, float(image_width)),
                "bottom": (desired_top + (local_face_box["bottom"] * square_side)) / max(1.0, float(image_height)),
            }
        )
        return mapped

    def _refine_detected_face_box(
        self,
        image: Any,
        face_box: dict[str, float],
    ) -> tuple[dict[str, float], dict[str, Any]]:
        width, height = image.size
        recrop_spec = self._square_face_redetect_spec(
            face_box,
            image_width=width,
            image_height=height,
        )
        if recrop_spec is None:
            return face_box, {"refined": False, "reason": "recrop-spec-unavailable"}

        cropped_payload = self._crop_centered_square(
            image,
            center_x_px=recrop_spec["center_x"],
            center_y_px=recrop_spec["center_y"],
            side_px=recrop_spec["side"],
        )
        if cropped_payload is None:
            return face_box, {"refined": False, "reason": "recrop-failed"}

        recropped_image, crop_payload = cropped_payload
        refined_box, refined_meta = self._detect_face_box(recropped_image)
        if refined_box is None:
            return face_box, {
                "refined": False,
                "reason": "redetect-failed",
                "recrop": crop_payload,
                "redetect": refined_meta,
            }

        mapped_box = self._map_face_box_from_crop(
            refined_box,
            crop_payload=crop_payload,
            image_width=width,
            image_height=height,
        )
        if mapped_box is None:
            return face_box, {
                "refined": False,
                "reason": "redetect-map-failed",
                "recrop": crop_payload,
                "redetect": refined_meta,
            }

        return mapped_box, {
            "refined": True,
            "recrop": crop_payload,
            "redetect": refined_meta,
            "original_face_box": face_box,
            "refined_face_box": mapped_box,
        }

    def _crop_face_region(
        self,
        image: Any,
        frame_hint: dict[str, Any] | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        width, height = image.size
        crop_meta: dict[str, Any] = {
            "strategy": "full-frame",
            "source_size": [width, height],
        }

        detected_face_box, detector_meta = self._detect_face_box(image)
        if detector_meta:
            crop_meta["autodetect"] = detector_meta
        if detected_face_box is not None:
            refined_face_box, refinement_meta = self._refine_detected_face_box(image, detected_face_box)
            crop_meta["autodetect_refinement"] = refinement_meta
            crop_spec = self._square_face_crop_spec(
                refined_face_box,
                image_width=width,
                image_height=height,
            )
            if crop_spec is not None:
                cropped_payload = self._crop_centered_square(
                    image,
                    center_x_px=crop_spec["center_x"],
                    center_y_px=crop_spec["center_y"],
                    side_px=crop_spec["side"],
                )
                if cropped_payload is not None:
                    cropped, crop_payload = cropped_payload
                    pixel_box = list(crop_payload.get("original_pixel_box") or crop_payload.get("pixel_box") or [])
                    crop_meta.update(
                        {
                            "strategy": "auto-face-detect",
                            "normalized_box": refined_face_box,
                            **crop_payload,
                        }
                    )
                    if pixel_box:
                        crop_meta["pixel_box"] = pixel_box
                    return cropped, crop_meta

        face_box = _normalize_face_box((frame_hint or {}).get("face_box"))
        if face_box is not None:
            crop_spec = self._square_face_crop_spec(
                face_box,
                image_width=width,
                image_height=height,
            )
            if crop_spec is not None:
                cropped_payload = self._crop_centered_square(
                    image,
                    center_x_px=crop_spec["center_x"],
                    center_y_px=crop_spec["center_y"],
                    side_px=crop_spec["side"],
                )
                if cropped_payload is not None:
                    cropped, crop_payload = cropped_payload
                    pixel_box = list(crop_payload.get("original_pixel_box") or crop_payload.get("pixel_box") or [])
                    crop_meta.update(
                        {
                            "strategy": "face-box",
                            "normalized_box": face_box,
                            **crop_payload,
                        }
                    )
                    if pixel_box:
                        crop_meta["pixel_box"] = pixel_box
                    return cropped, crop_meta

        crop_side = int(max(24, round(min(width, height) * 0.48)))
        center_x = width / 2.0
        center_y = height * 0.28
        cropped_payload = self._crop_centered_square(
            image,
            center_x_px=center_x,
            center_y_px=center_y,
            side_px=float(crop_side),
        )

        if cropped_payload is not None:
            cropped, crop_payload = cropped_payload
            pixel_box = list(crop_payload.get("original_pixel_box") or crop_payload.get("pixel_box") or [])
            crop_meta.update(
                {
                    "strategy": "upper-center-fallback-tight",
                    **crop_payload,
                }
            )
            if pixel_box:
                crop_meta["pixel_box"] = pixel_box
            return cropped, crop_meta

        return image, crop_meta

    def _prepare_input_batch(
        self,
        raw_bytes: bytes,
        frame_hint: dict[str, Any] | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        from io import BytesIO

        import numpy as np
        from PIL import Image

        width = max(1, int(self._input_shape[1] or 224))
        height = max(1, int(self._input_shape[0] or 224))

        with Image.open(BytesIO(raw_bytes)).convert("RGB") as image:
            cropped, crop_meta = self._crop_face_region(image, frame_hint)
            lanczos = _resampling_lanczos()
            resized = cropped.resize((width, height), resample=lanczos) if lanczos is not None else cropped.resize((width, height))
            input_batch = np.expand_dims(np.asarray(resized, dtype="float32"), axis=0)

        crop_meta["model_input_size"] = [width, height]
        return input_batch, crop_meta

    def _calibrate_prediction_output(
        self,
        *,
        dominant_label: str,
        dominant_confidence: float,
        top_predictions: list[dict[str, Any]],
        crop_meta: dict[str, Any],
        frame_hint: dict[str, Any] | None,
    ) -> tuple[str, float | None, dict[str, Any], str]:
        has_frame_hint = bool(
            isinstance(frame_hint, dict)
            and any(key in frame_hint for key in ("face_detected", "face_count", "looking_forward", "centered", "face_box"))
        )
        frame_quality = _frame_hint_quality(frame_hint) if has_frame_hint else 1.0
        face_area = _frame_hint_face_area(frame_hint) if has_frame_hint else 0.0
        metadata_updates: dict[str, Any] = {
            "raw_top_label": dominant_label,
            "raw_top_confidence": float(dominant_confidence),
            "prediction_margin": _prediction_margin(top_predictions),
            "reportable": True,
            "frame_quality": float(frame_quality),
            "frame_face_area": float(face_area),
            "raw_model_only_mode": _use_raw_model_only_mode(),
        }
        if _use_raw_model_only_mode():
            metadata_updates.update(
                {
                    "reportable": True,
                    "calibrated_label": dominant_label,
                    "calibrated_confidence": float(dominant_confidence),
                    "uncertainty_flags": [],
                    "report_weight": 1.0,
                }
            )
            return (
                dominant_label,
                float(dominant_confidence),
                metadata_updates,
                "The custom emotion model analyzed the latest candidate frame in raw model-only mode.",
            )

        uncertainty_flags: list[str] = []

        strategy = str(crop_meta.get("strategy", "") or "").strip().lower()
        detector_meta = dict(crop_meta.get("autodetect") or {})
        detector_name = str(detector_meta.get("detector", "") or "").strip().lower()
        refinement_meta = dict(crop_meta.get("autodetect_refinement") or {})
        hint_expression = str((frame_hint or {}).get("expression", "") or "").strip().lower()
        neutral_score = _prediction_score_for_label(top_predictions, "neutral")
        happy_score = _prediction_score_for_label(top_predictions, "happy")
        top2_score = 0.0
        if len(top_predictions) > 1:
            try:
                top2_score = max(0.0, float(top_predictions[1].get("score", 0.0) or 0.0))
            except Exception:
                top2_score = 0.0

        if strategy.startswith("upper-center-fallback"):
            uncertainty_flags.append("fallback_crop")
        if detector_name in {"no-face-detected", "opencv-haarcascade"} and int(detector_meta.get("detected_faces", 0) or 0) <= 0:
            uncertainty_flags.append("no_reliable_face_detection")
        if detector_name == "opencv-haarcascade":
            uncertainty_flags.append("weak_face_detector")
        if refinement_meta and not bool(refinement_meta.get("refined")):
            uncertainty_flags.append("face_refinement_failed")
        if dominant_confidence < _MIN_REPORTABLE_CONFIDENCE:
            uncertainty_flags.append("low_confidence")
        margin = float(metadata_updates["prediction_margin"])
        if margin < _MIN_REPORTABLE_MARGIN:
            uncertainty_flags.append("low_margin")
        if top2_score >= _MAX_STRONG_RUNNER_UP:
            uncertainty_flags.append("strong_runner_up")
        if has_frame_hint and frame_quality < _MIN_REPORTABLE_FRAME_QUALITY:
            uncertainty_flags.append("low_frame_quality")
        if has_frame_hint and face_area > 0 and face_area < _MIN_REPORTABLE_FACE_AREA:
            uncertainty_flags.append("small_face")
        if dominant_label == "sad":
            if hint_expression == "smiling":
                uncertainty_flags.append("sad_conflicts_with_smile")
            if neutral_score >= 0.28 and (dominant_confidence - neutral_score) < 0.18:
                uncertainty_flags.append("sad_close_to_neutral")
            if happy_score >= 0.14:
                uncertainty_flags.append("sad_conflicts_with_happy")

        if uncertainty_flags:
            calibrated_confidence = min(dominant_confidence, max(0.0, margin))
            metadata_updates.update(
                {
                    "reportable": False,
                    "calibrated_label": "uncertain",
                    "calibrated_confidence": float(calibrated_confidence),
                    "uncertainty_flags": uncertainty_flags,
                    "report_weight": 0.0,
                }
            )
            return (
                "uncertain",
                float(calibrated_confidence),
                metadata_updates,
                "The custom emotion model analyzed the latest frame, but the emotion label is uncertain.",
            )

        metadata_updates.update(
            {
                "calibrated_label": dominant_label,
                "calibrated_confidence": float(dominant_confidence),
                "uncertainty_flags": [],
                "report_weight": float(max(0.05, dominant_confidence * max(frame_quality, 0.5))),
            }
        )
        return (
            dominant_label,
            float(dominant_confidence),
            metadata_updates,
            "The custom emotion model analyzed the latest candidate frame.",
        )

    # --- Public interface ---

    def describe(self) -> EmotionAnalysis:
        try:
            self._ensure_assets_loaded()
            self._load_predict_fn()
            self._validate_model_behavior()
        except Exception as exc:
            return EmotionAnalysis(
                provider=self.provider,
                ready=False,
                summary="The custom emotion model is configured but not ready yet.",
                metadata={
                    "model_dir": str(self._model_root() or ""),
                    "reason": str(exc),
                },
            )

        if self._validation_error:
            if _allow_unverified_custom_model():
                return EmotionAnalysis(
                    provider=self.provider,
                    ready=True,
                    summary="The custom emotion model is forced on despite failing behavioral validation.",
                    metadata={
                        "model_dir": str(self._model_root() or ""),
                        "warning": self._validation_error,
                        "validation_bypassed": True,
                        **self._validation_metadata,
                    },
                )
            return EmotionAnalysis(
                provider=self.provider,
                ready=False,
                summary="The custom emotion model export is loaded but failed behavioral validation.",
                metadata={
                    "model_dir": str(self._model_root() or ""),
                    "reason": self._validation_error,
                    **self._validation_metadata,
                },
            )

        return EmotionAnalysis(
            provider=self.provider,
            ready=True,
            summary="The custom TensorFlow emotion model is ready for backend facial analysis.",
            metadata={
                "model_dir": str(self._model_root() or ""),
                "labels": list(self._labels),
                "input_shape": list(self._input_shape),
                "runtime_format": "keras" if self._keras_model is not None else "saved_model",
                "runtime_loader": self._keras_runtime,
                "raw_model_only_mode": _use_raw_model_only_mode(),
                **self._validation_metadata,
            },
        )

    def analyze_image_bytes(
        self,
        raw_bytes: bytes,
        *,
        frame_hint: dict[str, Any] | None = None,
    ) -> EmotionAnalysis:
        diag = self.describe()
        if not diag.ready:
            return diag

        try:
            input_batch, crop_meta = self._prepare_input_batch(raw_bytes, frame_hint)
            normalized_scores = self._predict_scores_from_batch(input_batch)

            score_map = {
                label: max(0.0, float(score)) * 100.0
                for label, score in zip(self._labels, normalized_scores)
            }

            top_index = max(range(len(normalized_scores)), key=lambda i: normalized_scores[i])
            dominant_label = self._labels[top_index]
            dominant_confidence = float(normalized_scores[top_index])

            top_predictions = [
                {"label": lbl, "score": float(sc)}
                for lbl, sc in sorted(
                    zip(self._labels, normalized_scores),
                    key=lambda x: x[1],
                    reverse=True,
                )[:5]
            ]
            report_label, report_confidence, calibration_metadata, summary = self._calibrate_prediction_output(
                dominant_label=dominant_label,
                dominant_confidence=dominant_confidence,
                top_predictions=top_predictions,
                crop_meta=crop_meta,
                frame_hint=frame_hint,
            )

            return EmotionAnalysis(
                provider=self.provider,
                ready=True,
                summary=summary,
                label=report_label,
                confidence=report_confidence,
                metadata={
                    "model_dir": str(self._model_root() or ""),
                    "raw_emotion": score_map,           # dict[label] = percentage
                    "raw_predictions": top_predictions, # list of normalized probabilities
                    "labels": list(self._labels),
                    "input_shape": list(self._input_shape),
                    "crop": crop_meta,
                    **calibration_metadata,
                },
            )
        except Exception as exc:
            return EmotionAnalysis(
                provider=self.provider,
                ready=False,
                summary="The custom emotion model could not analyze the latest frame.",
                metadata={
                    "model_dir": str(self._model_root() or ""),
                    "reason": str(exc),
                },
            )
