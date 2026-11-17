"""One-shot microphone capture and local Parakeet MLX transcription."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import tempfile
import threading
import wave
from typing import Callable

logger = logging.getLogger(__name__)
_parakeet_model = None
_parakeet_model_name: str | None = None


class VoiceInput:
    """Capture one spoken request and return its Parakeet transcript."""

    def __init__(
        self,
        on_transcript: Callable[[str], None],
        on_transcribing: Callable[[], None],
        on_error: Callable[[str], None],
        transcribe: Callable[[Path], str] | None = None,
    ) -> None:
        self.on_transcript = on_transcript
        self.on_transcribing = on_transcribing
        self.on_error = on_error
        self.transcribe = transcribe or self._transcribe
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._listen,
            name="max-voice-input",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _listen(self) -> None:
        audio_path: Path | None = None
        try:
            import numpy as np
            import sounddevice as sd

            with sd.InputStream(
                samplerate=16000,
                channels=1,
                dtype="int16",
                blocksize=1280,
            ) as stream:
                audio_path = self._record_utterance(stream, np)
            if audio_path is None or self._stop_event.is_set():
                return
            self.on_transcribing()
            transcript = self.transcribe(audio_path)
            audio_path = None  # _transcribe removes the temporary recording.
            if not self._stop_event.is_set():
                self.on_transcript(transcript)
        except Exception as exc:
            logger.exception("Voice capture or transcription failed")
            if not self._stop_event.is_set():
                self.on_error(str(exc))
        finally:
            if audio_path is not None:
                audio_path.unlink(missing_ok=True)

    def _record_utterance(self, stream, np) -> Path | None:
        sample_rate = 16000
        chunk_size = 1280
        speech_threshold = float(os.getenv("MAX_VOICE_RMS_THRESHOLD", "450"))
        start_timeout_chunks = int(10.0 * sample_rate / chunk_size)
        silence_limit_chunks = int(1.2 * sample_rate / chunk_size)
        max_chunks = int(30.0 * sample_rate / chunk_size)
        silence_chunks = 0
        chunks = []

        for index in range(max_chunks):
            if self._stop_event.is_set():
                return None
            audio, _overflowed = stream.read(chunk_size)
            chunk = np.asarray(audio, dtype=np.int16).reshape(-1)
            rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
            if not chunks and rms < speech_threshold:
                if index >= start_timeout_chunks:
                    raise TimeoutError("No speech detected. Run /voice and try again.")
                continue

            chunks.append(chunk)
            if rms < speech_threshold:
                silence_chunks += 1
                if silence_chunks >= silence_limit_chunks:
                    break
            else:
                silence_chunks = 0

        if not chunks:
            return None

        pcm_audio = np.concatenate(chunks).astype(np.int16, copy=False)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as audio_file:
            audio_path = Path(audio_file.name)
        try:
            with wave.open(str(audio_path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(pcm_audio.tobytes())
            return audio_path
        except Exception:
            audio_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _transcribe(audio_path: Path) -> str:
        global _parakeet_model, _parakeet_model_name
        try:
            from parakeet_mlx import from_pretrained

            model_name = os.getenv(
                "PARAKEET_MODEL", "mlx-community/parakeet-tdt-0.6b-v3"
            )
            if _parakeet_model is None or _parakeet_model_name != model_name:
                _parakeet_model = from_pretrained(model_name)
                _parakeet_model_name = model_name
            transcript = _parakeet_model.transcribe(str(audio_path)).text.strip()
            if not transcript:
                raise RuntimeError("Parakeet returned an empty transcript.")
            return transcript
        finally:
            audio_path.unlink(missing_ok=True)
