from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from core.config import AppSettings, CartesiaSettings, LLMSettings, STTSettings
from core.paths import ensure_data_dirs
from interview_ai.base import Intelligence
from orchestrator.session_store import JsonSessionStore, PostgresSessionStore, SessionStore

if TYPE_CHECKING:
    from interview_ai.langchain_provider import LangChainIntelligence
    from orchestrator.tech_workflow_support import TechnicalWorkflowSupport
    from voicee.stt import DeepgramNovaSTT
    from voicee.tts import CartesiaSonicTTS

SUPPORTED_LLM_BACKENDS = {"langchain"}


class SilentTTS:
    """No-op TTS for API mode (text only)."""

    def speak(self, text: str) -> None:
        return None


def build_intelligence(app_settings: AppSettings) -> Intelligence:
    backend = (app_settings.llm_backend or "langchain").strip().lower()
    if backend not in SUPPORTED_LLM_BACKENDS:
        supported = ", ".join(sorted(SUPPORTED_LLM_BACKENDS))
        raise ValueError(f"Unsupported LLM_BACKEND '{backend}'. Supported values: {supported}.")

    from interview_ai.langchain_provider import LangChainIntelligence

    settings: LLMSettings = app_settings.llm
    return LangChainIntelligence(
        api_key=settings.api_key,
        base_url=settings.base_url,
        model=settings.model,
        azure_endpoint=settings.azure_endpoint,
        azure_deployment=settings.azure_deployment,
        azure_api_version=settings.azure_api_version,
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
    )


def build_session_store(database_url: str) -> SessionStore:
    ensure_data_dirs()
    if database_url:
        return PostgresSessionStore(database_url)
    return JsonSessionStore()


def build_api_tts(settings: CartesiaSettings) -> CartesiaSonicTTS | None:
    from voicee.tts import CartesiaSonicTTS

    if not settings.api_key:
        return None
    return CartesiaSonicTTS(
        api_key=settings.api_key,
        model=settings.model,
        voice_id=settings.voice_id,
        language=settings.language,
        gate_event=None,
        mode="tts",
        verbose=False,
    )


def build_local_tts(settings: CartesiaSettings, gate_event: threading.Event) -> CartesiaSonicTTS:
    from voicee.tts import CartesiaSonicTTS

    return CartesiaSonicTTS(
        api_key=settings.api_key,
        model=settings.model,
        voice_id=settings.voice_id,
        language=settings.language,
        gate_event=gate_event,
        mode=settings.mode,
        verbose=settings.verbose,
    )


def build_emotion_analyzer(app_settings: AppSettings):
    from vision.emotion import CustomEmotionAnalyzer, NoopEmotionAnalyzer

    provider = app_settings.emotion.provider
    if provider == "custom" and app_settings.emotion.custom_model_dir is not None:
        return CustomEmotionAnalyzer(model_dir=app_settings.emotion.custom_model_dir)
    return NoopEmotionAnalyzer()


def build_orchestrator(
    *,
    app_settings: AppSettings,
    tts,
    session_store: SessionStore | None = None,
    intelligence: Intelligence | None = None,
) -> TechnicalWorkflowSupport:
    from orchestrator.langchain_orchestrator import LangChainTechOrchestrator

    resolved_store = session_store or build_session_store(app_settings.database_url)
    resolved_intelligence = intelligence or build_intelligence(app_settings)
    return LangChainTechOrchestrator(
        intelligence=resolved_intelligence,
        tts=tts,
        session_store=resolved_store,
        course_dir=app_settings.course_dir if app_settings.auto_ingest_courses else None,
    )


def build_stt(
    settings: STTSettings,
    orchestrator: TechnicalWorkflowSupport,
    session_id: str,
    gate_event: threading.Event,
) -> DeepgramNovaSTT:
    from voicee.stt import DeepgramNovaSTT

    return DeepgramNovaSTT(
        api_key=settings.api_key,
        orchestrator=orchestrator,
        language=settings.language,
        model=settings.model,
        gate_event=gate_event,
        session_id=session_id,
        mic_index=settings.mic_index,
        endpointing_ms=settings.endpointing_ms,
        utterance_end_ms=settings.utterance_end_ms,
        merge_window_s=settings.merge_window_s,
        continuation_window_s=settings.continuation_window_s,
    )
