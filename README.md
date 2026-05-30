# technique-agent

This folder contains the technical interview application space.

## Structure

- `backend/services/` for the independently deployable FastAPI services
- `infra/nginx/` for the API gateway routing rules
- `frontend/` for the technical interview UI
- `.env` for the technical backend runtime configuration

## Suggested local ports

- backend: `8001`
- frontend: `3001`

This workspace contains a technical interview application powered by LangChain.

Current architecture:

- `api-gateway` exposes the public backend API on port `8001`
- `interview-service` owns sessions, CV/doc ingestion, questions, scoring, and finalization
- `media-service` owns STT, live STT websocket, TTS, audio, vision, and proctoring observations
- `analytics-service` owns dashboard/history aggregation
- `reporting-service` owns PDF report generation
- `frontend` talks only to the gateway through `TECH_API_BASE_URL`

Run the microservice stack:

```powershell
docker compose up --build
```
