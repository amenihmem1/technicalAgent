import threading
import time
from datetime import datetime

from core.runtime import configure_runtime_verbosity

configure_runtime_verbosity()

from core.config import load_settings
from core.factories import build_intelligence, build_local_tts, build_orchestrator, build_stt


def main():
    settings = load_settings()

    if not settings.stt.api_key:
        raise RuntimeError("DEEPGRAM_API_KEY missing in .env")

    if settings.cartesia.mode != "print" and not settings.cartesia.api_key:
        raise RuntimeError("CARTESIA_API_KEY missing in .env")

    gate = threading.Event()
    gate.set()

    tts = build_local_tts(settings.cartesia, gate)
    intelligence = build_intelligence(settings)
    llm_diag = intelligence.healthcheck()
    llm_provider = str(llm_diag.get("provider") or settings.llm_backend or "unknown").strip()
    if llm_diag.get("ok"):
        print(
            f"[LLM] backend={llm_provider} endpoint={llm_diag['base_url']} model={llm_diag['model']} reachable=yes"
        )
        if llm_diag.get("model_available") is False:
            print(f"[LLM] warning: model '{llm_diag['model']}' not listed by server.")
            if llm_diag.get("available_models"):
                print(f"[LLM] available={', '.join(llm_diag['available_models'])}")
    else:
        print(
            f"[LLM] backend={llm_provider} endpoint={llm_diag['base_url']} model={llm_diag['model']} reachable=no"
        )
        print(f"[LLM] diagnostic: {llm_diag.get('error', 'unknown error')}")

    orchestrator = build_orchestrator(app_settings=settings, tts=tts, intelligence=intelligence)
    print("[Orchestrator] backend=langchain")
    print("[Experience] mode=voice-only")

    session_id = settings.session_id or f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    print(f"[Session] {session_id}")

    candidate_name = ""
    if settings.candidate_cv_path:
        try:
            cv_path = settings.candidate_cv_path
            raw_cv = cv_path.read_bytes()
            ingest_result = orchestrator.ingest_candidate_cv(
                session_id=session_id,
                filename=cv_path.name,
                raw_bytes=raw_cv,
            )
            profile = ingest_result.get("profile", {})
            if isinstance(profile, dict):
                candidate_name = str(profile.get("candidate_name", "")).strip()
            print(
                f"[CV] loaded={cv_path.name} chunks={ingest_result.get('chunks_count', 0)} "
                f"name={candidate_name or 'n/a'}"
            )
        except Exception as exc:
            print(f"[CV] warning: cannot ingest candidate CV from CANDIDATE_CV_PATH: {exc}")

    stt = build_stt(settings.stt, orchestrator, session_id, gate)
    print(f"[STT] provider=deepgram model={settings.stt.model} language={settings.stt.language}")

    # Speak first to avoid opening STT websocket with no audio.
    if candidate_name:
        welcome = f"Bonjour {candidate_name} ! Bienvenue a cet entretien. Pouvez-vous vous presenter ?"
    else:
        welcome = "Bonjour ! Bienvenue a cet entretien. Pouvez-vous vous presenter ?"
    tts.speak(welcome)
    stt.start()

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        stt.stop()
        print("Stopped.")


if __name__ == "__main__":
    main()
