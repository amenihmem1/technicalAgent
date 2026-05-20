from abc import ABC, abstractmethod
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any

from core.paths import SESSIONS_DIR, ensure_data_dirs, sanitize_storage_name

logger = logging.getLogger(__name__)
SESSION_SCHEMA_VERSION = 2


class SessionStore(ABC):
    @abstractmethod
    def load(self, session_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def save(self, session_id: str, payload: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_payloads(self, limit: int = 100) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def delete(self, session_id: str) -> bool:
        raise NotImplementedError


class JsonSessionStore(SessionStore):
    def __init__(self, base_dir: str | Path = SESSIONS_DIR):
        ensure_data_dirs()
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _safe_session_id(self, session_id: str) -> str:
        return sanitize_storage_name(session_id)

    def _path(self, session_id: str) -> Path:
        return self.base_dir / f"{self._safe_session_id(session_id)}.json"

    def _quarantine_corrupted_file(self, path: Path, reason: Exception) -> None:
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        quarantine_path = path.with_suffix(f".corrupt-{timestamp}.json")
        try:
            path.rename(quarantine_path)
            logger.warning(
                "Corrupted session payload moved to quarantine: original=%s quarantine=%s error=%s",
                path,
                quarantine_path,
                reason,
            )
        except Exception:
            logger.warning(
                "Unable to quarantine corrupted session payload: path=%s error=%s",
                path,
                reason,
                exc_info=True,
            )

    def _load_path(self, path: Path) -> dict[str, Any] | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._quarantine_corrupted_file(path, exc)
            return None
        if not isinstance(payload, dict):
            logger.warning("Ignoring non-dict session payload at %s", path)
            return None
        return payload

    def load(self, session_id: str) -> dict[str, Any] | None:
        path = self._path(session_id)
        if not path.exists():
            return None
        payload = self._load_path(path)
        if payload is None:
            return None
        payload.setdefault("schema_version", SESSION_SCHEMA_VERSION)
        payload.setdefault("session_id", path.stem)
        return payload

    def save(self, session_id: str, payload: dict[str, Any]) -> None:
        existing = self.load(session_id) or {}
        payload_with_meta = dict(payload)
        existing_history_meta = existing.get("history_meta")
        incoming_history_meta = payload_with_meta.get("history_meta")
        if isinstance(existing_history_meta, dict) and not isinstance(incoming_history_meta, dict):
            payload_with_meta["history_meta"] = dict(existing_history_meta)
        now_iso = datetime.utcnow().isoformat() + "Z"
        existing_created = str(existing.get("created_at", "") or "").strip()
        incoming_created = str(payload_with_meta.get("created_at", "") or "").strip()
        payload_with_meta["created_at"] = existing_created or incoming_created or now_iso
        payload_with_meta["updated_at"] = now_iso
        payload_with_meta["schema_version"] = SESSION_SCHEMA_VERSION
        payload_with_meta.setdefault("session_id", session_id)
        serialized = json.dumps(payload_with_meta, ensure_ascii=True, indent=2)
        self._path(session_id).write_text(serialized, encoding="utf-8")

    def list_payloads(self, limit: int = 100) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for path in sorted(self.base_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            if len(payloads) >= max(1, limit):
                break
            payload = self._load_path(path)
            if payload is None:
                continue
            payload.setdefault("schema_version", SESSION_SCHEMA_VERSION)
            payload.setdefault("session_id", path.stem)
            payloads.append(payload)

        payloads.sort(key=lambda item: str(item.get("updated_at", "") or ""), reverse=True)
        return payloads[: max(1, limit)]

    def delete(self, session_id: str) -> bool:
        path = self._path(session_id)
        if not path.exists():
            return False
        try:
            path.unlink()
            return True
        except Exception:
            return False


class PostgresSessionStore(SessionStore):
    def __init__(self, database_url: str):
        self.database_url = database_url
        try:
            import psycopg  # type: ignore
        except Exception as exc:
            raise RuntimeError(f"psycopg is required for PostgresSessionStore: {exc}") from exc
        self._psycopg = psycopg
        self._init_schema()

    def _connect(self):
        return self._psycopg.connect(self.database_url)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS interview_sessions (
                        session_id TEXT PRIMARY KEY,
                        payload JSONB NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            conn.commit()

    def load(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT payload FROM interview_sessions WHERE session_id = %s",
                    (session_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return row[0]

    def save(self, session_id: str, payload: dict[str, Any]) -> None:
        existing = self.load(session_id) or {}
        existing_history_meta = existing.get("history_meta")
        normalized_payload = dict(payload)
        if isinstance(existing_history_meta, dict) and not isinstance(normalized_payload.get("history_meta"), dict):
            normalized_payload["history_meta"] = dict(existing_history_meta)
        now_iso = datetime.utcnow().isoformat() + "Z"
        existing_created = str(existing.get("created_at", "") or "").strip()
        incoming_created = str(normalized_payload.get("created_at", "") or "").strip()
        normalized_payload["created_at"] = existing_created or incoming_created or now_iso
        normalized_payload["updated_at"] = now_iso
        normalized_payload["schema_version"] = SESSION_SCHEMA_VERSION
        normalized_payload.setdefault("session_id", session_id)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO interview_sessions (session_id, payload, updated_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (session_id)
                    DO UPDATE SET payload = EXCLUDED.payload, updated_at = NOW()
                    """,
                    (
                        session_id,
                        self._psycopg.types.json.Jsonb(normalized_payload),
                    ),
                )
            conn.commit()

    def list_payloads(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT payload
                    FROM interview_sessions
                    ORDER BY updated_at DESC
                    LIMIT %s
                    """,
                    (max(1, limit),),
                )
                rows = cur.fetchall()

        payloads: list[dict[str, Any]] = []
        for row in rows:
            payload = row[0] if row else None
            if isinstance(payload, dict):
                payloads.append(payload)
        return payloads

    def delete(self, session_id: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM interview_sessions WHERE session_id = %s", (session_id,))
                deleted = cur.rowcount > 0
            conn.commit()
        return deleted
