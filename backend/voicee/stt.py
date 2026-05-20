import threading
import queue
import time
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
    Microphone,
)

class DeepgramNovaSTT:
    """
    Microphone -> Deepgram -> texte final -> Orchestrator
    """

    def __init__(
        self,
        api_key: str,
        orchestrator,
        session_id: str,
        language: str = "fr",
        gate_event: threading.Event | None = None,
        mic_index: int | None = None,
        model: str = "nova-2",
        endpointing_ms: int = 500,
        utterance_end_ms: int = 1500,
        merge_window_s: float = 1.0,
        continuation_window_s: float = 1.8,
    ):
        self.orchestrator = orchestrator
        self.session_id = session_id
        self.buffer = ""
        self.gate_event = gate_event
        self.mic_index = mic_index
        self.work_queue: queue.Queue[str | None] = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_started = False
        self.merge_window_s = max(0.0, float(merge_window_s))
        self.continuation_window_s = max(0.0, float(continuation_window_s))

        self.client = DeepgramClient(
            api_key,
            DeepgramClientOptions(
                api_key=api_key,
                options={"keepalive": "true"},
            ),
        )
        self.connection = None
        self.started = False
        self.options = LiveOptions(
            model=model,
            language=language,
            encoding="linear16",
            channels=1,
            sample_rate=16000,
            interim_results=True,
            punctuate=True,
            vad_events=True,
            endpointing=endpointing_ms,
            utterance_end_ms=str(max(1000, utterance_end_ms)),
        )

        self.microphone = Microphone(self._push_audio, input_device_index=self.mic_index)

    def _looks_incomplete(self, text: str) -> bool:
        t = (text or "").strip()
        if not t:
            return True
        words = t.split()
        if len(words) < 7:
            return True
        if t[-1] not in ".!?":
            return True
        tail = words[-1].strip(".,;:!?").lower()
        connectors = {
            "et",
            "ou",
            "donc",
            "mais",
            "car",
            "pour",
            "avec",
            "dans",
            "sur",
            "de",
            "du",
            "des",
            "que",
            "qui",
            "dont",
            "si",
            "alors",
        }
        return tail in connectors

    def _ensure_connection(self):
        if self.connection is not None:
            return
        self.connection = self.client.listen.live.v("1")
        self.connection.on(LiveTranscriptionEvents.Open, self._on_open)
        self.connection.on(LiveTranscriptionEvents.Transcript, self._on_transcript)
        self.connection.on(LiveTranscriptionEvents.UtteranceEnd, self._on_utterance_end)
        self.connection.on(LiveTranscriptionEvents.Error, self._on_error)
        self.connection.on(LiveTranscriptionEvents.Close, self._on_close)

    def start(self):
        self._ensure_connection()
        opened = self.connection.start(self.options, addons={"no_delay": "true"})
        if not opened:
            raise RuntimeError("Unable to start Deepgram websocket STT.")

        print("Listening... (Ctrl+C to stop)")
        if not self.microphone.start():
            raise RuntimeError("Unable to start microphone. Install PyAudio.")
        if not self.worker_started:
            self.worker_thread.start()
            self.worker_started = True
        self.started = True

    def stop(self):
        try:
            if self.started:
                self.microphone.finish()
        except Exception:
            pass
        try:
            if self.connection is not None:
                self.connection.finish()
        except Exception:
            pass
        try:
            self.work_queue.put_nowait(None)
        except Exception:
            pass
        self.started = False

    def _push_audio(self, chunk: bytes):
        if self.connection is None:
            return
        # While TTS is speaking, push silence to keep websocket alive and avoid feedback.
        if self.gate_event is not None and not self.gate_event.is_set():
            self.connection.send(bytes(len(chunk)))
            return
        self.connection.send(chunk)

    def _flush_buffer(self):
        final_text = self.buffer.strip()
        self.buffer = ""
        if not final_text:
            return
        print(f"[Candidate]: {final_text}")
        self.work_queue.put(final_text)

    def _worker_loop(self):
        while True:
            item = self.work_queue.get()
            if item is None:
                return
            try:
                merged = [item]
                # Merge follow-up fragments that arrive after short silence gaps.
                while True:
                    try:
                        nxt = self.work_queue.get(timeout=self.merge_window_s)
                    except queue.Empty:
                        break
                    if nxt is None:
                        return
                    merged.append(nxt)

                merged_text = " ".join(x.strip() for x in merged if x and x.strip())

                # If the utterance still looks incomplete, wait continuation windows a bit longer.
                attempts = 0
                while merged_text and self._looks_incomplete(merged_text) and attempts < 2:
                    attempts += 1
                    try:
                        nxt = self.work_queue.get(timeout=self.continuation_window_s)
                    except queue.Empty:
                        break
                    if nxt is None:
                        return
                    merged_text = f"{merged_text} {nxt}".strip()
                    # Drain any immediate buffered follow-ups.
                    while True:
                        try:
                            nxt = self.work_queue.get_nowait()
                        except queue.Empty:
                            break
                        if nxt is None:
                            return
                        merged_text = f"{merged_text} {nxt}".strip()

                # Discard tiny fragments that are usually residual audio cuts.
                if merged_text and len(merged_text.split()) <= 2:
                    continue

                if merged_text:
                    self.orchestrator.handle_candidate_text(session_id=self.session_id, text=merged_text)
            except Exception as exc:
                print("Orchestrator worker error:", exc)

    def _on_open(self, *_args, **_kwargs):
        print("Deepgram STT connected")

    def _on_close(self, *_args, **_kwargs):
        print("Deepgram STT closed")

    def _on_error(self, _conn, error, **_kwargs):
        print("Deepgram STT error:", error)

    def _on_transcript(self, _conn, result, **_kwargs):
        try:
            alt = result.channel.alternatives[0]
            text = (alt.transcript or "").strip()
            if not text:
                return
            if result.is_final:
                self.buffer = f"{self.buffer} {text}".strip()
        except Exception as exc:
            print("Transcript handler error:", exc)

    def _on_utterance_end(self, *_args, **_kwargs):
        self._flush_buffer()
