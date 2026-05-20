# Frontend (Next.js)

This frontend lives under `technique-agent/frontend` and is part of the technical interview application.

The UI is aligned with the technical interview flow and shares the same product language as the backend.

## Run

```bash
cd technique-agent/frontend
npm install
npm run dev -- --port 3001
```

Open: `http://localhost:3001`

Backend required (FastAPI technical API):

```bash
# from project root
cd technique-agent/backend
uvicorn api_server:build_app --factory --host 127.0.0.1 --port 8001 --reload
```

Optional backend URL override for proxy routes:

```bash
# in technique-agent/frontend/.env.local
TECH_API_BASE_URL=http://127.0.0.1:8001
```

Optional public frontend URL for QR codes and share links:

```bash
# in technique-agent/frontend/.env.local
NEXT_PUBLIC_APP_URL=https://your-public-frontend.example
```

For phone testing on the same network, use a reachable host such as `http://192.168.x.x:3001` and start Next with a network host, for example:

```bash
npm run dev -- --hostname 0.0.0.0 --port 3001
```

The interviewer UI is currently voice-first. Cartesia is the only active TTS provider in the frontend flow.

## Purpose

This frontend provides a technical interview UI to:

- set `session_id`
- upload candidate CV (`pdf/doc/docx/txt/md/png/jpg/webp`) with OCR fallback for scanned files
- send candidate messages
- receive interviewer responses and final report summary

