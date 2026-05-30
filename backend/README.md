# technique-agent backend

Backend dedicated to the technical interview agent.

This backend powers the technical interview application as independently deployable FastAPI services.

## Microservices

- `infra/nginx/api-gateway.conf` routes public HTTP/WebSocket traffic to internal services.
- `services.interview.main:app` exposes session, interview, CV, docs, and finalization routes.
- `services.media.main:app` exposes STT, live STT, TTS, audio, vision, and proctoring routes.
- `services.analytics.main:app` exposes dashboard/history aggregation routes.
- `services.reporting.main:app` exposes report PDF routes.

## Responsibilities

- technical interview orchestration
- CV ingestion
- technical PDF ingestion
- technical RAG retrieval
- technical scoring
- technical final reporting

## Target API namespace

- `/tech/sessions`
- `/tech/sessions/{session_id}/message`
- `/tech/sessions/{session_id}/cv`
- `/tech/sessions/{session_id}/docs`
- `/tech/sessions/{session_id}/finalize`

## Suggested local port

- gateway: `8001`
- internal services: `8000` inside Docker network

## Deployment

The production microservice path is documented in `../docs/azure-microservices.md`.
The legacy single-backend workflow is kept as a manual fallback only and no longer runs on pushes to `main`.
