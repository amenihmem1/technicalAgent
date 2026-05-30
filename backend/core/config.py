from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from core.paths import BACKEND_ENV_FILE, COURSE_DIR, PROJECT_DIR, ROOT_ENV_FILE


def _read_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _read_int(name: str, default: int) -> int:
    return int(_read_str(name, str(default)))


def _read_float(name: str, default: float) -> float:
    return float(_read_str(name, str(default)))


def _read_first(names: tuple[str, ...], default: str = "") -> str:
    for name in names:
        raw = os.getenv(name)
        if raw is not None and raw.strip():
            return raw.strip()
    return default.strip()


def _read_int_first(names: tuple[str, ...], default: int) -> int:
    return int(_read_first(names, str(default)))


def _read_float_first(names: tuple[str, ...], default: float) -> float:
    return float(_read_first(names, str(default)))


def _read_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class LLMSettings:
    api_key: str
    base_url: str
    model: str
    azure_endpoint: str
    azure_deployment: str
    azure_api_version: str
    max_tokens: int
    temperature: float


@dataclass(frozen=True, slots=True)
class CartesiaSettings:
    api_key: str
    model: str
    voice_id: str
    language: str
    mode: str
    verbose: bool


@dataclass(frozen=True, slots=True)
class STTSettings:
    api_key: str
    language: str
    model: str
    mic_index: int | None
    endpointing_ms: int
    utterance_end_ms: int
    merge_window_s: float
    continuation_window_s: float
    request_timeout_s: float
    connect_timeout_s: float
    read_timeout_s: float
    write_timeout_s: float
    max_attempts: int
    retry_backoff_s: float


@dataclass(frozen=True, slots=True)
class EmotionSettings:
    provider: str
    custom_model_dir: Path | None


@dataclass(frozen=True, slots=True)
class AppSettings:
    llm_backend: str
    llm: LLMSettings
    cartesia: CartesiaSettings
    stt: STTSettings
    emotion: EmotionSettings
    database_url: str
    session_id: str
    candidate_cv_path: Path | None
    course_dir: Path | None
    auto_ingest_courses: bool


def load_backend_env() -> None:
    if ROOT_ENV_FILE.exists():
        load_dotenv(ROOT_ENV_FILE, override=False)
    if BACKEND_ENV_FILE.exists():
        load_dotenv(BACKEND_ENV_FILE, override=False)


def _resolve_optional_path(raw_value: str) -> Path | None:
    if not raw_value:
        return None
    candidate = Path(raw_value).expanduser()
    return candidate if candidate.is_absolute() else (PROJECT_DIR / candidate)


def _discover_default_custom_emotion_model_dir() -> Path | None:
    emotion_models_dir = PROJECT_DIR / "backend" / "data" / "models" / "emotion"
    if not emotion_models_dir.exists():
        return None
    candidates = sorted(
        [path for path in emotion_models_dir.iterdir() if path.is_dir()],
        key=lambda path: path.name,
        reverse=True,
    )
    return candidates[0] if candidates else None


def load_settings() -> AppSettings:
    load_backend_env()

    candidate_cv_raw = _read_str("CANDIDATE_CV_PATH")
    candidate_cv_path: Path | None = None
    if candidate_cv_raw:
        raw_path = Path(candidate_cv_raw).expanduser()
        candidate_cv_path = raw_path if raw_path.is_absolute() else (PROJECT_DIR / raw_path)

    mic_index_raw = _read_str("MIC_DEVICE_INDEX")
    mic_index = int(mic_index_raw) if mic_index_raw else None
    course_dir_raw = _read_str("COURSE_DIR")
    custom_model_dir = _resolve_optional_path(_read_str("CUSTOM_EMOTION_MODEL_DIR")) or _discover_default_custom_emotion_model_dir()
    configured_provider = _read_str("EMOTION_BACKEND_PROVIDER", "").lower()
    emotion_provider = "custom" if custom_model_dir is not None else "none"
    if configured_provider and configured_provider not in {"custom", "none"}:
        print(f"[Emotion] Ignoring unsupported provider '{configured_provider}'. Custom-only mode is enforced.")

    return AppSettings(
        llm_backend=_read_str("LLM_BACKEND", "langchain").lower(),
        llm=LLMSettings(
            api_key=_read_first(("LLM_API_KEY", "AZURE_OPENAI_API_KEY", "LANGCHAIN_API_KEY", "GROQ_API_KEY")),
            base_url=_read_first(
                ("LLM_BASE_URL", "LANGCHAIN_BASE_URL", "GROQ_BASE_URL"),
                "https://api.groq.com/openai/v1",
            ),
            model=_read_first(
                ("LLM_MODEL", "LANGCHAIN_MODEL", "GROQ_MODEL"),
                "openai/gpt-oss-20b",
            ),
            azure_endpoint=_read_str("AZURE_OPENAI_ENDPOINT"),
            azure_deployment=_read_str("AZURE_OPENAI_DEPLOYMENT"),
            azure_api_version=_read_str("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
            max_tokens=_read_int_first(
                ("LLM_MAX_TOKENS", "LANGCHAIN_MAX_TOKENS", "GROQ_MAX_TOKENS"),
                320,
            ),
            temperature=_read_float_first(
                ("LLM_TEMPERATURE", "LANGCHAIN_TEMPERATURE", "GROQ_TEMPERATURE"),
                0.7,
            ),
        ),
        cartesia=CartesiaSettings(
            api_key=_read_str("CARTESIA_API_KEY"),
            model=_read_str("CARTESIA_MODEL", _read_str("TTS_MODEL", "sonic")),
            voice_id=_read_str("CARTESIA_VOICE_ID", "694f9389-aac1-45b6-b726-9d9369183238"),
            language=_read_str("CARTESIA_LANGUAGE", "fr"),
            mode=_read_str("TTS_MODE", "tts").lower(),
            verbose=_read_bool("TTS_VERBOSE", True),
        ),
        stt=STTSettings(
            api_key=_read_str("DEEPGRAM_API_KEY"),
            language=_read_str("STT_LANGUAGE", "fr"),
            model=_read_str("STT_MODEL", "nova-3"),
            mic_index=mic_index,
            endpointing_ms=_read_int("STT_ENDPOINTING_MS", 1400),
            utterance_end_ms=_read_int("STT_UTTERANCE_END_MS", 3200),
            merge_window_s=_read_float("STT_MERGE_WINDOW_S", 0.35),
            continuation_window_s=_read_float("STT_CONTINUATION_WINDOW_S", 1.8),
            request_timeout_s=_read_float("STT_REQUEST_TIMEOUT_S", 90.0),
            connect_timeout_s=_read_float("STT_CONNECT_TIMEOUT_S", 15.0),
            read_timeout_s=_read_float("STT_READ_TIMEOUT_S", 90.0),
            write_timeout_s=_read_float("STT_WRITE_TIMEOUT_S", 90.0),
            max_attempts=max(1, _read_int("STT_MAX_ATTEMPTS", 2)),
            retry_backoff_s=max(0.0, _read_float("STT_RETRY_BACKOFF_S", 1.25)),
        ),
        emotion=EmotionSettings(
            provider=emotion_provider,
            custom_model_dir=custom_model_dir,
        ),
        database_url=_read_str("DATABASE_URL"),
        session_id=_read_str("SESSION_ID"),
        candidate_cv_path=candidate_cv_path,
        course_dir=_resolve_optional_path(course_dir_raw) if course_dir_raw else COURSE_DIR,
        auto_ingest_courses=_read_bool("AUTO_INGEST_COURSES", True),
    )
