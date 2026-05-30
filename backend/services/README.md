# Backend Services

This directory contains deployable FastAPI entrypoints for each technical backend microservice.

| Service | Module | Responsibility |
| --- | --- | --- |
| Interview | `services.interview.main:app` | sessions, CV/docs, messages, finalization |
| Media | `services.media.main:app` | STT, live STT, TTS, audio, vision, proctoring |
| Analytics | `services.analytics.main:app` | dashboard/history aggregation |
| Reporting | `services.reporting.main:app` | PDF reports |

Shared domain modules stay in `core`, `orchestrator`, `voicee`, `vision`, `reporting`, and `interview_ai`.

