import os
import platform
import shutil
import subprocess
import tempfile
import threading
import time

import httpx
try:
    import winsound  # type: ignore
except ImportError:
    winsound = None


FRENCH_TTS_MARKERS = (
    " je ",
    " vous ",
    " nous ",
    " entretien ",
    " parcours ",
    " merci ",
    " avec ",
    " dans ",
    " est ",
    " suis ",
    " pour ",
    " bonjour ",
)

ENGLISH_TTS_MARKERS = (
    " i ",
    " you ",
    " we ",
    " interview ",
    " background ",
    " thank ",
    " with ",
    " in ",
    " am ",
    " for ",
    " hello ",
)


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _detect_tts_language(text: str) -> str:
    sample = f" {(text or '').strip().lower()} "
    if not sample.strip():
        return "fr"

    fr_score = sum(1 for marker in FRENCH_TTS_MARKERS if marker in sample)
    en_score = sum(1 for marker in ENGLISH_TTS_MARKERS if marker in sample)
    return "en" if en_score > fr_score else "fr"


class CartesiaSonicTTS:
    API_URL = "https://api.cartesia.ai/tts/bytes"
    API_VERSION = "2025-04-16"

    def __init__(
        self,
        api_key: str,
        model: str,
        voice_id: str,
        language: str = "fr",
        sample_rate: int = 24000,
        encoding: str = "pcm_s16le",
        gate_event: threading.Event | None = None,
        mode: str = "tts",
        verbose: bool = True,
        timeout_s: float | None = None,
        retry_attempts: int | None = None,
        retry_backoff_s: float | None = None,
        trust_env: bool | None = None,
        verify_tls: bool | None = None,
    ):
        self.mode = (mode or "tts").lower()
        self.api_key = api_key
        self.model = model
        self.voice_id = voice_id
        self.language = language
        self.sample_rate = sample_rate
        self.encoding = encoding
        self.gate_event = gate_event
        self.verbose = bool(verbose)
        self.timeout_s = float(timeout_s if timeout_s is not None else os.getenv("CARTESIA_TIMEOUT_S", "45"))
        self.retry_attempts = max(
            1,
            int(retry_attempts if retry_attempts is not None else os.getenv("CARTESIA_RETRY_ATTEMPTS", "3")),
        )
        self.retry_backoff_s = max(
            0.0,
            float(
                retry_backoff_s
                if retry_backoff_s is not None
                else os.getenv("CARTESIA_RETRY_BACKOFF_S", "0.75")
            ),
        )
        self.trust_env = trust_env if trust_env is not None else _env_flag("CARTESIA_TRUST_ENV", False)
        self.verify_tls = verify_tls if verify_tls is not None else _env_flag("CARTESIA_TLS_VERIFY", True)
        try:
            self._client = httpx.Client(
                timeout=self.timeout_s,
                trust_env=self.trust_env,
                verify=self.verify_tls,
                http2=True,
            )
        except ImportError:
            self._client = httpx.Client(
                timeout=self.timeout_s,
                trust_env=self.trust_env,
                verify=self.verify_tls,
            )

    def _play_wav_file(self, path: str) -> None:
        system = platform.system().lower()

        if system == "windows":
            if winsound is not None:
                try:
                    winsound.PlaySound(path, winsound.SND_FILENAME)
                    return
                except Exception:
                    pass

            ps_path = path.replace("'", "''")
            script = (
                "Add-Type -AssemblyName presentationCore;"
                "$p = New-Object System.Media.SoundPlayer;"
                f"$p.SoundLocation = '{ps_path}';"
                "$p.Load();"
                "$p.PlaySync();"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                return

        player_commands = []
        if system == "darwin":
            player_commands.append(["afplay", path])
        else:
            player_commands.extend(
                [
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
                    ["paplay", path],
                    ["aplay", path],
                    ["play", "-q", path],
                ]
            )

        for command in player_commands:
            if shutil.which(command[0]):
                result = subprocess.run(
                    command,
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if result.returncode == 0:
                    return

        raise RuntimeError("No supported local audio player found for WAV playback")

    def _fix_wav_header(self, audio: bytes) -> bytes:
        if not audio or len(audio) < 44 or audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
            return audio

        data_idx = audio.find(b"data")
        if data_idx == -1 or data_idx + 8 > len(audio):
            return audio

        patched = bytearray(audio)
        riff_size = len(audio) - 8
        data_size = len(audio) - (data_idx + 8)
        patched[4:8] = int(riff_size).to_bytes(4, byteorder="little", signed=False)
        patched[data_idx + 4:data_idx + 8] = int(data_size).to_bytes(4, byteorder="little", signed=False)
        return bytes(patched)

    def _resolve_language(self, text: str, language: str | None = None) -> str:
        requested = (language or self.language or "fr").strip().lower()
        if requested in {"multi", "multilingual", "auto", "detect"}:
            return _detect_tts_language(text)
        return requested or "fr"

    def synthesize_bytes(self, text: str, language: str | None = None) -> bytes:
        resolved_language = self._resolve_language(text, language)
        headers = {
            "Cartesia-Version": self.API_VERSION,
            "X-API-Key": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model_id": self.model,
            "transcript": text,
            "voice": {
                "mode": "id",
                "id": self.voice_id,
            },
            "language": resolved_language,
            "output_format": {
                "container": "wav",
                "encoding": self.encoding,
                "sample_rate": self.sample_rate,
            },
        }

        last_exc: httpx.TransportError | None = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                response = self._client.post(self.API_URL, headers=headers, json=payload)
                response.raise_for_status()
                audio = self._fix_wav_header(response.content)
                break
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt >= self.retry_attempts:
                    raise
                if self.verbose:
                    print(
                        "[TTS] transport retry "
                        f"{attempt}/{self.retry_attempts} trust_env={self.trust_env} "
                        f"verify_tls={self.verify_tls}: {exc}"
                    )
                time.sleep(self.retry_backoff_s * attempt)
        else:
            if last_exc is not None:
                raise last_exc

        if not audio or len(audio) < 2000:
            raise RuntimeError("Cartesia returned empty/too small audio payload")
        return audio

    def _print_only(self, text: str) -> None:
        print(f"[Interviewer]: {text}")
        if self.verbose:
            print("[TTS] mode=print")

    def _speak_with_cartesia(self, text: str) -> None:
        audio = self.synthesize_bytes(text)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as file_handle:
            file_handle.write(audio)
            path = file_handle.name

        try:
            print(f"[Interviewer]: {text}")
            self._play_wav_file(path)
            if self.verbose:
                print(
                    "[TTS] mode=cartesia "
                    f"model={self.model} voice={self.voice_id} language={self._resolve_language(text)} bytes={len(audio)}"
                )
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    def speak(self, text: str) -> None:
        if not text:
            return

        if self.gate_event is not None:
            self.gate_event.clear()

        try:
            if self.mode == "print":
                self._print_only(text)
                return

            self._speak_with_cartesia(text)
        except Exception as exc:
            print(f"[TTS] fallback after failure: {exc}")
            self._print_only(text)
        finally:
            if self.gate_event is not None:
                self.gate_event.set()
