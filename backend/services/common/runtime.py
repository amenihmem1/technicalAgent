import asyncio
import json
import logging
import time
from typing import Any, Dict

import httpx
from deepgram import DeepgramClient, DeepgramClientOptions, LiveOptions, LiveTranscriptionEvents
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel

try:
    from deepgram.clients.listen.v1.websocket import async_client as deepgram_async_ws_client
except Exception:  # pragma: no cover - keep runtime-compatible with older SDK layouts.
    deepgram_async_ws_client = None

from core.runtime import configure_runtime_verbosity

configure_runtime_verbosity()

from core.config import load_settings
from core.factories import (
    SilentTTS,
    build_api_tts,
    build_emotion_analyzer,
    build_orchestrator,
    build_session_store,
)
from orchestrator.guardrails import require_cv_uploaded_for_message
from interview_ai.base import LLMRateLimitError
from services.common.history import (
    build_candidate_history_groups as _build_candidate_history_groups,
    build_candidate_history_key as _build_candidate_history_key,
    build_session_history_item as _build_session_history_item,
    normalize_history_title as _normalize_history_title,
)
from vision.emotion import build_visual_llm_context, emotion_analysis_to_dict, update_visual_observations
from voicee.observations import build_audio_llm_context, update_audio_observations

logger = logging.getLogger(__name__)
_deepgram_live_transport_patched = False
_DEEPGRAM_SILENCE_FRAME = b"\x00\x00" * 320


def _configure_deepgram_live_transport() -> None:
    global _deepgram_live_transport_patched

    if _deepgram_live_transport_patched or deepgram_async_ws_client is None:
        return

    # The SDK already sends Deepgram-level keepalive frames. Disabling the
    # transport ping avoids noisy upstream disconnects on slower networks.
    deepgram_async_ws_client.PING_INTERVAL = None
    _deepgram_live_transport_patched = True


def _format_live_stt_error(error: Any) -> str:
    description = str(getattr(error, "description", "") or "").strip()
    message = str(getattr(error, "message", "") or "").strip()
    fallback = str(error or "").strip()
    combined = ". ".join(part for part in [description, message] if part)
    normalized = (combined or fallback).lower()

    if "keepalive ping timeout" in normalized:
        return "Deepgram live stream timed out. Please retry the microphone."
    if "did not receive audio data or a text message within the timeout window" in normalized or "net0001" in normalized:
        return "Deepgram live stream went idle for too long. Please keep speaking or retry the microphone."

    return combined or fallback or "Live STT unavailable."


def _is_recoverable_live_stt_error(error: Any) -> bool:
    description = str(getattr(error, "description", "") or "").strip().lower()
    message = str(getattr(error, "message", "") or "").strip().lower()
    fallback = str(error or "").strip().lower()
    normalized = " ".join(part for part in [description, message, fallback] if part)
    return any(
        marker in normalized
        for marker in (
            "keepalive ping timeout",
            "did not receive audio data or a text message within the timeout window",
            "net0001",
        )
    )

class CandidateMessage(BaseModel):
    text: str
    candidate_name: str = "Candidate"
    sender_name: str = ""


class TTSRequest(BaseModel):
    text: str
    language: str = ""


class AudioObservationRequest(BaseModel):
    duration_seconds: float = 0.0
    word_count: int = 0
    filler_count: int = 0
    speech_rate_wpm: float = 0.0
    volume_score: float = 0.0
    silence_ratio: float = 0.0
    pause_count: int = 0
    pitch_hz: float = 0.0
    pitch_variation_hz: float = 0.0
    energy_label: str = ""
    pace_label: str = ""
    hesitation_label: str = ""


class ProctoringEventRequest(BaseModel):
    reason: str = "unknown"
    message: str = ""
    count: int = 0
    time: str = ""


class SessionMetaUpdateRequest(BaseModel):
    title: str | None = None
    pinned: bool | None = None
    archived: bool | None = None


class SessionPreferencesUpdateRequest(BaseModel):
    preferred_input_mode: str = "voice"


class FinalizeSessionRequest(BaseModel):
    preferred_input_mode: str = "voice"
    finalized_by: str = "user"


class LiveTranscriptAccumulator:
    def __init__(self) -> None:
        self._final_text = ""

    @staticmethod
    def _normalize_token(token: str) -> str:
        return token.strip(" \t\r\n.,;:!?()[]{}\"'").lower()

    @classmethod
    def _merge_text(cls, existing: str, incoming: str) -> str:
        left = " ".join(str(existing or "").split()).strip()
        right = " ".join(str(incoming or "").split()).strip()

        if not left:
            return right
        if not right:
            return left

        left_cmp = left.lower()
        right_cmp = right.lower()
        if right_cmp.startswith(left_cmp):
            return right
        if left_cmp.startswith(right_cmp):
            return left

        left_words = left.split()
        right_words = right.split()
        max_overlap = min(len(left_words), len(right_words))
        for overlap in range(max_overlap, 0, -1):
            left_tail = [cls._normalize_token(token) for token in left_words[-overlap:]]
            right_head = [cls._normalize_token(token) for token in right_words[:overlap]]
            if left_tail == right_head and any(left_tail):
                return " ".join([*left_words, *right_words[overlap:]]).strip()

        return f"{left} {right}".strip()

    def add_result(self, *, transcript: str, is_final: bool, speech_final: bool) -> list[dict[str, Any]]:
        clean = (transcript or "").strip()
        if not clean:
            return []

        if is_final:
            self._final_text = self._merge_text(self._final_text, clean)
            combined = self._final_text
            if not combined:
                return []
            if speech_final:
                self._final_text = ""
                return [{"type": "final", "text": combined}]
            return [{"type": "interim", "text": combined}]

        combined = self._merge_text(self._final_text, clean)
        if not combined:
            return []
        return [{"type": "interim", "text": combined}]

    def flush(self) -> str:
        combined = self._final_text.strip()
        self._final_text = ""
        return combined


async def _parse_json_response(response: httpx.Response) -> tuple[str, dict[str, Any] | None]:
    raw = response.text
    try:
        payload = response.json()
        return raw, payload if isinstance(payload, dict) else None
    except Exception:
        return raw, None


def _normalize_stt_language(value: str | None, default: str = "fr") -> str:
    raw = str(value or "").strip().lower()
    if raw in {"fr", "en", "multi"}:
        return raw
    fallback = str(default or "").strip().lower()
    if fallback in {"fr", "en", "multi"}:
        return fallback
    return "fr"


def _resolve_candidate_name(payload: CandidateMessage) -> str:
    return (payload.candidate_name or payload.sender_name or "Candidate").strip() or "Candidate"


def _clamp_pct(value: float) -> int:
    try:
        numeric = float(value)
    except Exception:
        numeric = 0.0
    return max(0, min(100, round(numeric)))


def _update_session_history_meta(
    *,
    session_store,
    session_id: str,
    title: str | None = None,
    pinned: bool | None = None,
    archived: bool | None = None,
) -> dict[str, Any] | None:
    payload = session_store.load(session_id)
    if not isinstance(payload, dict):
        return None

    history_meta = payload.get("history_meta")
    normalized_meta = dict(history_meta) if isinstance(history_meta, dict) else {}

    if title is not None:
        cleaned_title = _normalize_history_title(title)
        if cleaned_title:
            normalized_meta["title"] = cleaned_title
        else:
            normalized_meta.pop("title", None)
    if pinned is not None:
        normalized_meta["pinned"] = bool(pinned)
    if archived is not None:
        normalized_meta["archived"] = bool(archived)

    payload["history_meta"] = normalized_meta
    session_store.save(session_id, payload)
    return session_store.load(session_id) or payload


def _build_stress_context(
    audio_context: dict[str, Any],
    response_language: str,
) -> dict[str, Any]:
    audio_metrics = dict(audio_context.get("metrics") or {})
    audio_flags = set(audio_context.get("heuristic_flags") or [])
    is_en = str(response_language).strip().lower() == "en"

    silence_pct = float(audio_metrics.get("silence_pct_avg", 0) or 0)
    pause_count = float(audio_metrics.get("pause_count_avg", 0) or 0)
    pause_rate_per_min = float(audio_metrics.get("pause_rate_per_min_avg", 0) or 0)
    filler_density = float(audio_metrics.get("filler_density_pct", 0) or 0)
    speech_rate = float(audio_metrics.get("speech_rate_wpm_avg", 0) or 0)
    utterance_count = int(audio_metrics.get("utterance_count", 0) or 0)
    dominant_hesitation = str(audio_metrics.get("dominant_hesitation", "") or "").strip().lower()
    audio_sample_limited = utterance_count <= 1 or "analyse_vocale_insuffisante" in audio_flags

    pause_pressure = 0.0
    hesitation_pressure = 0.0
    vocal_tension = 0.0
    if not audio_sample_limited:
        pause_pressure = min(100.0, (silence_pct * 1.15) + (pause_rate_per_min * 1.35))
        hesitation_pressure = min(100.0, filler_density * 12.0)
        if dominant_hesitation == "moderate":
            hesitation_pressure += 10.0
        elif dominant_hesitation == "noticeable":
            hesitation_pressure += 18.0
        if "hesitations_verbales" in audio_flags:
            hesitation_pressure += 8.0
        hesitation_pressure = min(100.0, hesitation_pressure)

        if "tension_vocale_apparente" in audio_flags:
            vocal_tension += 28.0
        if "pauses_marquees" in audio_flags:
            vocal_tension += 10.0
        if speech_rate >= 165:
            vocal_tension += min(16.0, (speech_rate - 165.0) * 0.55)
        vocal_tension += min(12.0, filler_density * 2.8)
        if dominant_hesitation == "moderate":
            vocal_tension += 4.0
        elif dominant_hesitation == "noticeable":
            vocal_tension += 8.0
        vocal_tension = min(100.0, vocal_tension)

    if audio_sample_limited:
        stress_score = 0
    else:
        stress_score = _clamp_pct(
            (vocal_tension * 0.48)
            + (pause_pressure * 0.28)
            + (hesitation_pressure * 0.24)
        )

    if stress_score >= 65:
        band = "high" if is_en else "eleve"
    elif stress_score >= 40:
        band = "moderate" if is_en else "modere"
    else:
        band = "light" if is_en else "leger"

    if audio_sample_limited:
        summary = (
            "Vocal delivery reading is limited because the audio sample is too short."
            if is_en
            else "La lecture du delivery vocal reste limitee car l'echantillon audio est trop court."
        )
    else:
        summary = (
            "Vocal delivery cues remain secondary and should be read with caution."
            if is_en
            else "Les indices de delivery vocal restent secondaires et doivent etre lus avec prudence."
        )
        if stress_score < 40:
            summary = (
                "Vocal delivery remains controlled overall."
                if is_en
                else "Le delivery vocal reste globalement maitrise."
            )
        elif stress_score < 65:
            summary = (
                "Some moderate pressure cues appear in the voice without becoming dominant."
                if is_en
                else "Quelques indices moderes de pression apparaissent dans la voix, sans devenir dominants."
            )

    factors = []
    if not audio_sample_limited:
        factors.extend(
            [
                {
                    "key": "vocal",
                    "label": "Apparent vocal stress" if is_en else "Stress vocal apparent",
                    "value": _clamp_pct(vocal_tension),
                    "detail": "Pace + tension cues" if is_en else "Debit + indices de tension",
                },
                {
                    "key": "pauses",
                    "label": "Pause pressure" if is_en else "Pression des pauses",
                    "value": _clamp_pct(pause_pressure),
                    "detail": (
                        f"{_clamp_pct(silence_pct)}% silence / {round(pause_rate_per_min, 1)} pauses/min"
                        if is_en
                        else f"{_clamp_pct(silence_pct)}% silence / {round(pause_rate_per_min, 1)} pauses/min"
                    ),
                },
                {
                    "key": "hesitation",
                    "label": "Hesitation pressure" if is_en else "Pression des hesitations",
                    "value": _clamp_pct(hesitation_pressure),
                    "detail": (
                        f"{round(filler_density, 1)}% fillers density"
                        if is_en
                        else f"{round(filler_density, 1)}% densite de fillers"
                    ),
                },
            ]
        )

    return {
        "score": stress_score,
        "band": band,
        "summary": summary,
        "factors": factors,
        "confidence_note": (
            "Derived from browser-side vocal metrics only."
            if is_en
            else "Derive uniquement des metriques vocales capturees cote navigateur."
        ),
    }


def _build_insights_advice_context(
    orchestrator,
    *,
    visual_context: dict[str, Any],
    audio_context: dict[str, Any],
    stress_context: dict[str, Any],
    response_language: str,
) -> dict[str, Any] | None:
    try:
        return orchestrator.intelligence.generate_insights_advice(
            visual_context=visual_context,
            audio_context=audio_context,
            stress_context=stress_context,
            response_language=response_language,
        )
    except Exception:
        logger.warning("Unable to generate insights advice from LLM", exc_info=True)
        return None


def _build_session_insights_context(
    orchestrator,
    *,
    session_id: str,
    response_language: str,
) -> dict[str, Any]:
    cached = orchestrator.get_cached_insights(session_id, response_language=response_language)
    if isinstance(cached, dict) and cached:
        return cached

    session = orchestrator._get_or_create_session(session_id)
    visual_context = build_visual_llm_context(session.visual_observations, response_language)
    audio_context = build_audio_llm_context(session.audio_observations, response_language)
    stress_context = _build_stress_context(audio_context, response_language)
    insights_advice = _build_insights_advice_context(
        orchestrator,
        visual_context=visual_context,
        audio_context=audio_context,
        stress_context=stress_context,
        response_language=response_language,
    )
    return orchestrator.store_cached_insights(
        session_id,
        response_language=response_language,
        visual_context=visual_context,
        audio_context=audio_context,
        stress_context=stress_context,
        insights_advice=insights_advice,
    )


def _build_session_final_report_context(
    orchestrator,
    *,
    session_id: str,
    response_language: str,
) -> dict[str, Any] | None:
    session = orchestrator._get_or_create_session(session_id)
    if session.final_report is None:
        return None

    stored_language = str(session.response_language or "").strip().lower() or "fr"
    if stored_language == response_language:
        return session.final_report

    original_language = session.response_language
    try:
        session.response_language = response_language
        return orchestrator._build_final_report(session)
    finally:
        session.response_language = original_language


def build_app(service_name: str = "all") -> FastAPI:
    settings = load_settings()
    service_name = (service_name or "all").strip().lower()
    app = FastAPI(title="SUBUL Technical Service Runtime", version="0.1.0")

    # Add CORS middleware
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    state_services = {"all", "interview"}
    session_store = None
    orchestrator = None
    if service_name in state_services:
        try:
            session_store = build_session_store(settings.database_url)
            if settings.database_url:
                print("[SessionStore] PostgreSQL enabled")
        except Exception as exc:
            print(f"[SessionStore] PostgreSQL unavailable, fallback JSON store: {exc}")
            session_store = build_session_store("")
        orchestrator = build_orchestrator(app_settings=settings, tts=SilentTTS(), session_store=session_store)

    tts_engine = build_api_tts(settings.cartesia) if service_name == "all" else None

    vision_analyzers = []
    if service_name == "all":
        emotion_analyzer = build_emotion_analyzer(settings)
        if emotion_analyzer.provider != "none":
            vision_analyzers.append(emotion_analyzer)

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {"status": "ok"}

    @app.get("/tech/sessions")
    def list_sessions(limit: int = 60) -> Dict[str, Any]:
        try:
            logger.info(f"[API] GET /tech/sessions limit={limit}")
            limit_int = max(1, min(int(limit or 60), 200))
            logger.info(f"[API] Loading {limit_int} payloads from session store")
            payloads = session_store.list_payloads(limit=limit_int)
            logger.info(f"[API] Loaded {len(payloads)} payloads, building history groups")
            result = _build_candidate_history_groups(payloads)
            logger.info(f"[API] Built {len(result.get('sessions', []))} sessions and {len(result.get('candidates', []))} candidates")
            return result
        except Exception as e:
            logger.error(f"[API] Error loading sessions: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to load sessions: {str(e)}")

    @app.patch("/tech/sessions/{session_id}/meta")
    def update_session_meta(session_id: str, payload: SessionMetaUpdateRequest) -> Dict[str, Any]:
        updated = _update_session_history_meta(
            session_store=session_store,
            session_id=session_id,
            title=payload.title,
            pinned=payload.pinned,
            archived=payload.archived,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Session introuvable.")
        item = _build_session_history_item(updated)
        if item is None:
            raise HTTPException(status_code=500, detail="Session metadata could not be rebuilt.")
        return {"status": "ok", "session": item}

    @app.patch("/tech/sessions/{session_id}/preferences")
    def update_session_preferences(session_id: str, payload: SessionPreferencesUpdateRequest) -> Dict[str, Any]:
        session = orchestrator.set_preferred_input_mode(session_id, payload.preferred_input_mode)
        return {
            "status": "ok",
            "session_id": session.session_id,
            "preferred_input_mode": session.preferred_input_mode,
            "interview_status": session.interview_status,
        }

    @app.delete("/tech/sessions/{session_id}")
    def delete_session(session_id: str) -> Dict[str, Any]:
        existed_in_memory = session_id in getattr(orchestrator, "sessions", {})
        if existed_in_memory:
            orchestrator.sessions.pop(session_id, None)
        deleted = session_store.delete(session_id)
        if not deleted and not existed_in_memory:
            raise HTTPException(status_code=404, detail="Session introuvable.")
        return {"status": "ok", "deleted": True, "session_id": session_id}

    @app.post("/tech/sessions/{session_id}/audio")
    def record_candidate_audio_observations(session_id: str, payload: AudioObservationRequest) -> Dict[str, Any]:
        session = orchestrator._get_or_create_session(session_id)
        audio_observations = update_audio_observations(session.audio_observations, payload.model_dump())
        orchestrator.record_audio_observations(session_id, audio_observations)
        return {
            "status": "ok",
            "session_id": session_id,
            "audio_observations": audio_observations,
        }

    @app.post("/tech/sessions/{session_id}/vision")
    async def analyze_candidate_vision(
        session_id: str,
        file: UploadFile = File(...),
        face_detected: str = Form("false"),
        centered: str = Form("false"),
        looking_forward: str = Form("false"),
        expression: str = Form(""),
        posture: str = Form(""),
        face_count: str = Form("0"),
        objects: str = Form("[]"),
        face_box_left: str = Form(""),
        face_box_top: str = Form(""),
        face_box_right: str = Form(""),
        face_box_bottom: str = Form(""),
    ) -> Dict[str, Any]:
        try:
            raw = await file.read()
            if not raw:
                raise HTTPException(status_code=400, detail="Image vide.")

            def parse_bool(value: str) -> bool:
                return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

            def parse_int(value: str) -> int:
                try:
                    return int(float(str(value or "0").strip() or "0"))
                except Exception:
                    return 0

            def parse_float(value: str) -> float | None:
                try:
                    raw_value = str(value or "").strip()
                    return float(raw_value) if raw_value else None
                except Exception:
                    return None

            mediapipe_payload: dict[str, Any] = {
                "face_detected": parse_bool(face_detected),
                "centered": parse_bool(centered),
                "looking_forward": parse_bool(looking_forward),
                "expression": str(expression or "").strip(),
                "posture": str(posture or "").strip(),
                "face_count": parse_int(face_count),
            }
            try:
                parsed_objects = json.loads(objects or "[]")
            except Exception:
                parsed_objects = []
            if isinstance(parsed_objects, list):
                mediapipe_payload["objects"] = parsed_objects
            face_box_values = {
                "left": parse_float(face_box_left),
                "top": parse_float(face_box_top),
                "right": parse_float(face_box_right),
                "bottom": parse_float(face_box_bottom),
            }
            if all(value is not None for value in face_box_values.values()):
                mediapipe_payload["face_box"] = face_box_values

            session = orchestrator._get_or_create_session(session_id)
            provider_results = [analyzer.analyze_image_bytes(raw, frame_hint=mediapipe_payload) for analyzer in vision_analyzers]
            visual_observations = update_visual_observations(
                session.visual_observations,
                mediapipe=mediapipe_payload,
                provider_results=provider_results,
            )
            orchestrator.record_visual_observations(session_id, visual_observations)
            return {
                "status": "ok",
                "session_id": session_id,
                "providers": [emotion_analysis_to_dict(result) for result in provider_results],
                "visual_observations": visual_observations,
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Vision analysis failed: {str(e)}")

    @app.post("/tech/sessions/{session_id}/proctoring")
    def record_proctoring_event(session_id: str, payload: ProctoringEventRequest) -> Dict[str, Any]:
        try:
            events = orchestrator.record_proctoring_event(session_id, payload.model_dump())
            return {
                "status": "ok",
                "session_id": session_id,
                "proctoring_events": events,
                "proctoring_alerts_count": len(events),
            }
        except Exception as exc:
            logger.exception("Proctoring event failed for session %s", session_id, exc_info=exc)
            raise HTTPException(status_code=500, detail="Unable to record proctoring event.")

    @app.post("/tech/sessions/{session_id}/finalize")
    def finalize_session(session_id: str, payload: FinalizeSessionRequest) -> Dict[str, Any]:
        state = orchestrator._get_or_create_session(session_id)
        if not state.turns and not state.cv_uploaded:
            raise HTTPException(status_code=400, detail="Impossible de finaliser une session vide.")
        try:
            output = orchestrator.finalize_session(
                session_id,
                finalized_by=payload.finalized_by,
                preferred_input_mode=payload.preferred_input_mode,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Echec finalisation entretien: {exc}") from exc
        return output.model_dump()

    @app.post("/tech/sessions/{session_id}/message")
    def handle_message(session_id: str, payload: CandidateMessage) -> Dict[str, Any]:
        start = time.perf_counter()
        state = orchestrator._get_or_create_session(session_id)
        require_cv_uploaded_for_message(state)
        try:
            out = orchestrator.handle_candidate_text(
                session_id=session_id,
                text=payload.text,
                candidate_name=_resolve_candidate_name(payload),
            )
            logger.info(
                "API /tech/sessions/%s/message total_ms=%.1f",
                session_id,
                (time.perf_counter() - start) * 1000,
            )
            return out.model_dump()
        except HTTPException:
            raise
        except LLMRateLimitError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Echec traitement message technique: {exc}") from exc

    @app.post("/tech/sessions/{session_id}/cv")
    async def upload_cv(session_id: str, file: UploadFile = File(...)) -> Dict[str, Any]:
        filename = (file.filename or "").strip()
        if not filename:
            raise HTTPException(status_code=400, detail="Nom de fichier invalide.")
        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="Fichier vide.")
        try:
            result = orchestrator.ingest_candidate_cv(session_id=session_id, filename=filename, raw_bytes=raw)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Echec ingestion CV: {exc}") from exc
        profile = result.get("profile")
        profile = profile if isinstance(profile, dict) else {}
        result["candidate_key"] = _build_candidate_history_key(profile, session_id)
        return result

    @app.post("/tech/sessions/{session_id}/docs")
    async def upload_supporting_document(session_id: str, file: UploadFile = File(...)) -> Dict[str, Any]:
        filename = (file.filename or "").strip()
        if not filename:
            raise HTTPException(status_code=400, detail="Nom de fichier invalide.")
        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="Fichier vide.")
        try:
            return orchestrator.ingest_supporting_document(
                session_id=session_id,
                filename=filename,
                raw_bytes=raw,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Echec ingestion document technique: {exc}") from exc

    @app.post("/tech/stt")
    async def speech_to_text(file: UploadFile = File(...), language: str | None = None) -> Dict[str, Any]:
        if not settings.stt.api_key:
            raise HTTPException(status_code=500, detail="DEEPGRAM_API_KEY manquant sur le serveur.")

        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="Fichier audio vide.")

        content_type = (file.content_type or "audio/webm").strip()
        resolved_language = (language or settings.stt.language).strip()
        model = settings.stt.model
        url = f"https://api.deepgram.com/v1/listen?model={model}&language={resolved_language}&smart_format=true&punctuate=true"
        headers = {
            "Authorization": f"Token {settings.stt.api_key}",
            "Content-Type": content_type,
        }

        async def _send_stt_request() -> httpx.Response:
            timeout = httpx.Timeout(
                settings.stt.request_timeout_s,
                connect=settings.stt.connect_timeout_s,
                read=settings.stt.read_timeout_s,
                write=settings.stt.write_timeout_s,
            )
            async with httpx.AsyncClient(timeout=timeout) as client:
                return await client.post(url, headers=headers, content=raw)

        max_attempts = max(1, int(settings.stt.max_attempts or 1))
        retry_backoff_s = max(0.0, float(settings.stt.retry_backoff_s or 0.0))

        try:
            last_timeout_exc: httpx.TimeoutException | None = None
            resp: httpx.Response | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    resp = await _send_stt_request()
                except httpx.TimeoutException as exc:
                    last_timeout_exc = exc
                    if attempt >= max_attempts:
                        raise
                    logger.warning(
                        "Deepgram STT timeout on attempt %s/%s for content_type=%s language=%s size=%s bytes; retrying",
                        attempt,
                        max_attempts,
                        content_type,
                        resolved_language,
                        len(raw),
                    )
                    if retry_backoff_s > 0:
                        await asyncio.sleep(retry_backoff_s * attempt)
                    continue

                if resp.status_code != 408 or attempt >= max_attempts:
                    break

                logger.warning(
                    "Deepgram STT returned 408 on attempt %s/%s for content_type=%s language=%s size=%s bytes; retrying",
                    attempt,
                    max_attempts,
                    content_type,
                    resolved_language,
                    len(raw),
                )
                if retry_backoff_s > 0:
                    await asyncio.sleep(retry_backoff_s * attempt)

            if resp is None:
                if last_timeout_exc is not None:
                    raise last_timeout_exc
                raise HTTPException(status_code=502, detail="STT request did not produce a response.")

            if resp.status_code >= 400:
                raw_error = resp.text[:240]
                lowered_error = raw_error.lower()
                if "corrupt or unsupported data" in lowered_error:
                    friendly_detail = (
                        "Audio invalide ou format non supporte pour la transcription."
                        if resolved_language.lower().startswith("fr")
                        else "Invalid audio or unsupported format for transcription."
                    )
                    raise HTTPException(status_code=502, detail=friendly_detail)
                if resp.status_code == 408:
                    friendly_detail = (
                        "Le service de transcription a expire avant de recevoir un audio complet. Reessayez avec un enregistrement plus court."
                        if resolved_language.lower().startswith("fr")
                        else "The transcription service timed out before receiving a complete audio payload. Retry with a shorter recording."
                    )
                    raise HTTPException(status_code=504, detail=friendly_detail)
                raise HTTPException(status_code=502, detail=f"Deepgram error {resp.status_code}: {raw_error}")
            data = resp.json()
            transcript = (
                data.get("results", {})
                .get("channels", [{}])[0]
                .get("alternatives", [{}])[0]
                .get("transcript", "")
            )
            return {"text": (transcript or "").strip()}
        except HTTPException:
            raise
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=504,
                detail=(
                    "Le service de transcription a mis trop de temps a repondre apres plusieurs tentatives."
                    if resolved_language.lower().startswith("fr")
                    else "The transcription service took too long to respond after multiple attempts."
                ),
            ) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"STT backend failed: {exc}") from exc

    @app.websocket("/ws/tech/stt/{session_id}")
    async def tech_live_stt_ws(websocket: WebSocket, session_id: str):
        await websocket.accept()
        _configure_deepgram_live_transport()

        if not settings.stt.api_key:
            await websocket.send_json({"type": "error", "detail": "DEEPGRAM_API_KEY manquant sur le serveur."})
            await websocket.close(code=1011)
            return

        resolved_language = _normalize_stt_language(
            websocket.query_params.get("language"),
            settings.stt.language,
        )
        accumulator = LiveTranscriptAccumulator()
        deepgram = DeepgramClient(
            settings.stt.api_key,
            DeepgramClientOptions(
                api_key=settings.stt.api_key,
                options={"keepalive": "true"},
            ),
        )
        connection: Any | None = None
        keepalive_task: asyncio.Task[None] | None = None
        pending_flush_task: asyncio.Task[None] | None = None
        last_deepgram_activity_at = time.monotonic()
        deepgram_ready = False
        ready_sent = False

        async def _safe_send(payload: dict[str, Any]) -> None:
            try:
                await websocket.send_json(payload)
            except RuntimeError:
                return
            except WebSocketDisconnect:
                return
            except Exception:
                return

        async def _finish_deepgram_connection() -> None:
            nonlocal connection, deepgram_ready
            current = connection
            connection = None
            deepgram_ready = False
            if current is None:
                return
            try:
                await current.finish()
            except Exception:
                pass

        async def _start_deepgram_connection(*, emit_ready: bool) -> bool:
            nonlocal connection, last_deepgram_activity_at, deepgram_ready, ready_sent

            client_factory = getattr(deepgram.listen, "asyncwebsocket", None) or deepgram.listen.asynclive
            next_connection = client_factory.v("1")
            next_connection.on(LiveTranscriptionEvents.Open, _on_open)
            next_connection.on(LiveTranscriptionEvents.Transcript, _on_transcript)
            next_connection.on(LiveTranscriptionEvents.UtteranceEnd, _on_utterance_end)
            next_connection.on(LiveTranscriptionEvents.Error, _on_error)

            opened = await next_connection.start(options)
            if not opened:
                return False

            connection = next_connection
            deepgram_ready = True
            last_deepgram_activity_at = time.monotonic()

            if emit_ready and not ready_sent:
                ready_sent = True
                await _safe_send(
                    {
                        "type": "ready",
                        "session_id": session_id,
                        "language": resolved_language,
                        "model": settings.stt.model,
                    }
                )

            return True

        async def _restart_deepgram_connection(reason: str) -> bool:
            logger.info("Restarting Deepgram live STT for session %s: %s", session_id, reason)
            await _finish_deepgram_connection()
            return await _start_deepgram_connection(emit_ready=False)

        async def _send_to_deepgram(payload: str | bytes, *, allow_restart: bool = True) -> bool:
            nonlocal last_deepgram_activity_at

            if connection is None or not deepgram_ready:
                if not allow_restart or not await _restart_deepgram_connection("connection-not-ready"):
                    logger.warning("Live STT Deepgram connection unavailable for session %s", session_id)
                    return False

            sent = await connection.send(payload)
            if sent:
                last_deepgram_activity_at = time.monotonic()
                return True

            logger.warning("Live STT Deepgram send failed for session %s", session_id)
            if allow_restart and await _restart_deepgram_connection("send-failed"):
                resent = await _send_to_deepgram(payload, allow_restart=False)
                if resent:
                    return True
            return False

        async def _on_open(_conn, _open=None, **_kwargs):
            return

        async def _flush_pending_final() -> None:
            text = accumulator.flush()
            if text:
                await _safe_send({"type": "final", "text": text})

        def _cancel_pending_flush() -> None:
            nonlocal pending_flush_task
            if pending_flush_task is None:
                return
            pending_flush_task.cancel()
            pending_flush_task = None

        def _schedule_pending_flush(delay_s: float = 1.4) -> None:
            nonlocal pending_flush_task
            _cancel_pending_flush()

            async def _delayed_flush() -> None:
                try:
                    await asyncio.sleep(delay_s)
                    await _flush_pending_final()
                except asyncio.CancelledError:
                    return

            pending_flush_task = asyncio.create_task(_delayed_flush())

        async def _on_transcript(_conn, result=None, **_kwargs):
            if result is None:
                return
            try:
                alternatives = getattr(getattr(result, "channel", None), "alternatives", []) or []
                if not alternatives:
                    return
                transcript = str(getattr(alternatives[0], "transcript", "") or "").strip()
                payloads = accumulator.add_result(
                    transcript=transcript,
                    is_final=bool(getattr(result, "is_final", False)),
                    speech_final=bool(getattr(result, "speech_final", False)),
                )
                for payload in payloads:
                    if payload.get("type") == "final":
                        _cancel_pending_flush()
                    await _safe_send(payload)
                if bool(getattr(result, "is_final", False)) and not bool(getattr(result, "speech_final", False)):
                    _schedule_pending_flush()
                if bool(getattr(result, "speech_final", False)):
                    _cancel_pending_flush()
                    await _flush_pending_final()
            except Exception as exc:
                logger.warning("Live STT transcript handler failed for session %s: %s", session_id, exc)

        async def _on_utterance_end(_conn, _utterance_end=None, **_kwargs):
            _cancel_pending_flush()
            await _flush_pending_final()

        async def _on_error(_conn, error=None, **_kwargs):
            logger.warning("Deepgram live STT error for session %s: %s", session_id, error)
            if _is_recoverable_live_stt_error(error):
                return
            await _safe_send({"type": "error", "detail": _format_live_stt_error(error)})

        async def _deepgram_keepalive_loop() -> None:
            while True:
                await asyncio.sleep(1.0)
                try:
                    if time.monotonic() - last_deepgram_activity_at < 1.5:
                        continue
                    if connection is None or not deepgram_ready:
                        await _restart_deepgram_connection("keepalive-connection-not-ready")
                        continue
                    kept_alive = await _send_to_deepgram(_DEEPGRAM_SILENCE_FRAME, allow_restart=False)
                    if kept_alive:
                        last_deepgram_activity_at = time.monotonic()
                        continue
                    if not await _restart_deepgram_connection("keepalive-failed"):
                        return
                except Exception:
                    if not await _restart_deepgram_connection("keepalive-exception"):
                        return

        options = LiveOptions(
            model=settings.stt.model,
            language=resolved_language,
            punctuate=True,
            smart_format=True,
            interim_results=True,
            vad_events=True,
            endpointing=settings.stt.endpointing_ms,
            utterance_end_ms=str(max(1000, settings.stt.utterance_end_ms)),
            encoding="linear16",
            channels=1,
            sample_rate=16000,
        )

        try:
            opened = await _start_deepgram_connection(emit_ready=True)
            if not opened:
                await _safe_send({"type": "error", "detail": "Unable to start Deepgram live STT."})
                await websocket.close(code=1011)
                return
            keepalive_task = asyncio.create_task(_deepgram_keepalive_loop())

            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    break

                raw_audio = message.get("bytes")
                if raw_audio:
                    if not await _send_to_deepgram(raw_audio):
                        await _safe_send({"type": "error", "detail": "Live STT stream disconnected."})
                        break
                    continue

                text_message = str(message.get("text") or "").strip().lower()
                if text_message == "ping":
                    await _safe_send({"type": "pong"})
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.exception("Live STT websocket failed for session %s", session_id)
            await _safe_send({"type": "error", "detail": f"Live STT backend failed: {exc}"})
        finally:
            _cancel_pending_flush()
            if keepalive_task is not None:
                keepalive_task.cancel()
                try:
                    await keepalive_task
                except asyncio.CancelledError:
                    pass
            try:
                await _flush_pending_final()
            except Exception:
                pass
            await _finish_deepgram_connection()

    @app.post("/tech/tts")
    def text_to_speech(payload: TTSRequest):
        start = time.perf_counter()
        text = (payload.text or "").strip()
        language = (payload.language or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="Texte vide pour TTS.")

        if tts_engine is None:
            raise HTTPException(status_code=500, detail="CARTESIA_API_KEY manquant sur le serveur.")

        try:
            audio = tts_engine.synthesize_bytes(text, language=language or None)
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:240] if exc.response is not None else str(exc)
            raise HTTPException(status_code=502, detail=f"Cartesia error: {detail}") from exc
        except httpx.TransportError as exc:
            raise HTTPException(
                status_code=502,
                detail=(
                    "Cartesia transport error: "
                    f"{exc}. "
                    "Vous pouvez tester CARTESIA_TRUST_ENV=true si votre reseau impose un proxy."
                ),
            ) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"TTS backend failed: {exc}") from exc

        logger.info("API /tech/tts total_ms=%.1f text_len=%d", (time.perf_counter() - start) * 1000, len(text))
        return Response(content=audio, media_type="audio/wav")

    @app.get("/tech/sessions/{session_id}")
    def get_session(session_id: str, include_insights: bool = False, language: str = "") -> Dict[str, Any]:
        state = orchestrator._get_or_create_session(session_id)  # internal state access for quick API bootstrap
        persisted_payload = session_store.load(session_id) or {}
        requested_language = str(language or "").strip().lower()
        response_language = requested_language if requested_language in {"fr", "en"} else (state.response_language or "fr").strip().lower() or "fr"
        final_report = _build_session_final_report_context(
            orchestrator,
            session_id=session_id,
            response_language=response_language,
        )
        insights_context = (
            _build_session_insights_context(
                orchestrator,
                session_id=session_id,
                response_language=response_language,
            )
            if include_insights
            else {}
        )
        return {
            "session_id": state.session_id,
            "candidate_key": _build_candidate_history_key(state.cv_profile, state.session_id),
            "last_question_index": state.last_question_index,
            "turns_count": len(state.turns),
            "turns": state.turns,
            "final_report": final_report,
            "cv_uploaded": state.cv_uploaded,
            "cv_profile": state.cv_profile,
            "documents": state.documents,
            "response_language": response_language,
            "updated_at": str(persisted_payload.get("updated_at", "") or ""),
            "interview_status": state.interview_status,
            "finalized_at": state.finalized_at,
            "finalized_by": state.finalized_by,
            "preferred_input_mode": "voice",
            "audio_observations": state.audio_observations,
            "visual_observations": state.visual_observations,
            "visual_context": insights_context.get("visual_context"),
            "audio_context": insights_context.get("audio_context"),
            "stress_context": insights_context.get("stress_context"),
            "insights_advice": insights_context.get("insights_advice"),
            "proctoring_events": state.proctoring_events,
            "proctoring_alerts_count": len(state.proctoring_events),
        }

    @app.websocket("/ws/tech/{session_id}")
    async def tech_ws(websocket: WebSocket, session_id: str):
        await websocket.accept()
        try:
            while True:
                candidate_text = await websocket.receive_text()
                try:
                    out = orchestrator.handle_candidate_text(
                        session_id=session_id,
                        text=candidate_text,
                        candidate_name="Candidate",
                    )
                    await websocket.send_json(out.model_dump())
                except LLMRateLimitError as exc:
                    await websocket.send_json({"error": str(exc), "status": 429})
        except WebSocketDisconnect:
            return

    return app




