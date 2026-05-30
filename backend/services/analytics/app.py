from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from core.config import load_settings
from core.factories import build_session_store
from services.common.history import build_candidate_history_groups


def build_analytics_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(title="SUBUL Technical Analytics Service", version="0.1.0")

    try:
        session_store = build_session_store(settings.database_url)
    except Exception:
        session_store = build_session_store("")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "analytics"}

    @app.get("/")
    def root() -> dict[str, str]:
        return {"service": "SUBUL Technical Analytics Service", "status": "ok"}

    @app.get("/tech/dashboard")
    def dashboard(limit: int = 200) -> dict[str, Any]:
        payloads = session_store.list_payloads(limit=max(1, min(int(limit or 200), 500)))
        return build_candidate_history_groups(payloads)

    return app


