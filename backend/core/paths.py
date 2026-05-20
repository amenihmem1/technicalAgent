from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
COURSE_DIR = DATA_DIR / "course"
SESSIONS_DIR = DATA_DIR / "sessions"
REPORTS_DIR = DATA_DIR / "reports"
ROOT_ENV_FILE = PROJECT_DIR / ".env"
BACKEND_ENV_FILE = BACKEND_DIR / ".env"


def sanitize_storage_name(value: str, fallback: str = "session") -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in value).strip("_")
    return safe or fallback


def ensure_data_dirs() -> None:
    COURSE_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
