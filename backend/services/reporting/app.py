from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from core.config import load_settings
from core.factories import build_session_store
from reporting.pdf_report import build_candidate_insights_pdf, build_candidate_report_pdf


def build_reporting_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(title="SUBUL Technical Reporting Service", version="0.1.0")

    try:
        session_store = build_session_store(settings.database_url)
    except Exception:
        session_store = build_session_store("")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "reporting"}

    @app.get("/")
    def root() -> dict[str, str]:
        return {"service": "SUBUL Technical Reporting Service", "status": "ok"}

    @app.get("/tech/sessions/{session_id}/report.pdf")
    def download_report_pdf(session_id: str):
        payload = session_store.load(session_id)
        if not payload:
            raise HTTPException(status_code=404, detail="Session introuvable.")
        if not payload.get("final_report"):
            raise HTTPException(status_code=400, detail="Rapport final non disponible.")

        pdf_path = build_candidate_report_pdf(session_id=session_id, payload=payload)
        return FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
            filename=f"{session_id}-technical-report.pdf",
        )

    @app.get("/tech/sessions/{session_id}/insights-report.pdf")
    def download_insights_report_pdf(session_id: str):
        payload = session_store.load(session_id)
        if not payload:
            raise HTTPException(status_code=404, detail="Session introuvable.")
        if not payload.get("final_report"):
            raise HTTPException(status_code=400, detail="Rapport final non disponible.")

        pdf_path = build_candidate_insights_pdf(session_id=session_id, payload=payload)
        return FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
            filename=f"{session_id}-insights-vocaux.pdf",
        )

    return app
