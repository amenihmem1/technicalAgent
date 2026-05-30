# SUBUL Technical Microservices Architecture

## Services

| Service | Code entrypoint | Responsibility | Public routes through gateway |
| --- | --- | --- | --- |
| `api-gateway` | Nginx | Single backend entrypoint and route dispatch | `http://localhost:8001` |
| `interview-service` | `services.interview.main:app` | Technical session lifecycle, CV/docs ingestion, messages, WebSocket interview flow | `/tech/sessions...`, `/ws/tech/...` |
| `media-service` | `services.media.main:app` | STT, live STT, TTS, vision, audio, and proctoring signals | `/tech/stt`, `/ws/tech/stt...`, `/tech/tts`, selected `/tech/sessions/{id}/...` routes |
| `analytics-service` | `services.analytics.main:app` | Technical dashboard and history aggregation | `/tech/dashboard...` |
| `reporting-service` | `services.reporting.main:app` | Technical PDF reports and insights reports | `/tech/sessions/{id}/report.pdf`, `/tech/sessions/{id}/insights-report.pdf` |
| `frontend` | Next.js | Next.js application | `http://localhost:3001` |

## Runtime Flow

1. The browser calls the Next.js API routes.
2. Next.js forwards backend calls to `TECH_API_BASE_URL`.
3. In Docker, `TECH_API_BASE_URL` points to `http://api-gateway:8000`.
4. Nginx routes each path to the matching backend service.
5. Each backend service starts from its own Python module under `backend/services/*/main.py`.
6. Lightweight services use service-specific Python dependency files instead of the full AI/media dependency set.

## Current Split

The service boundary is deployable now. `analytics-service` and `reporting-service` have standalone FastAPI apps with slim dependency files. `interview-service` and `media-service` still reuse the shared technical runtime because they own the heaviest orchestration, speech, vision, and document-processing paths.

For production, prefer PostgreSQL through `DATABASE_URL` so service containers share state without relying on local filesystem data.
