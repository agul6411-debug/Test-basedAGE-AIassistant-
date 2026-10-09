"""Faster-Whisper Speech-to-Text engine.

Security Rule 3:
Transcribed speech is untrusted input.
Audio data stays in memory only.
"""

import time
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

from core.logger import get_logger

logger = get_logger("voice.stt")


class SpeechToText:
    """Offline Speech-to-Text transcriber using faster-whisper base.en on CPU."""

    def __init__(self, model_dir: str | Path | None = None) -> None:
        """Initialize faster-whisper model.

        Args:
            model_dir: Path to downloaded base.en model directory. Defaults to models/whisper-base.en.
        """
        path = Path(model_dir) if model_dir else Path("models/whisper-base.en")
        if not path.exists():
            raise FileNotFoundError(f"Whisper model directory not found at {path}. Run model downloader first.")

        logger.info("Loading Faster-Whisper base.en (CPU, int8) from %s...", path)
        t0 = time.perf_counter()
        self._model = WhisperModel(
            model_size_or_path=str(path),
            device="cpu",
            compute_type="int8",
            cpu_threads=4,
        )
        load_time = time.perf_counter() - t0
        logger.info("Faster-Whisper model loaded in %.2f seconds.", load_time)

    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe in-memory PCM audio to text.

        Args:
            audio_data: 1D NumPy array of audio (int16 or float32).
            sample_rate: Audio sampling frequency in Hz (default 16000).

        Returns:
            Transcribed English text string.
        """
        if audio_data is None or len(audio_data) == 0:
            return ""

        # Normalize int16 PCM to float32 [-1.0, 1.0] as required by Whisper
        if audio_data.dtype == np.int16:
            audio_float = audio_data.astype(np.float32) / 32768.0
        else:
            audio_float = audio_data.astype(np.float32)

        t_start = time.perf_counter()
        segments, info = self._model.transcribe(
            audio_float,
            language="en",
            beam_size=1,  # Greedy / beam_size=1 for lowest latency on CPU
            initial_prompt="Hey AGE, stop, okey stop, okay stop, ruko, chup, open notepad, calculator, chrome, edge, vscode, word, excel, powerpoint, paint, downloads, documents, desktop, youtube, volume, awaz, brightness, roshni, kholo, band karo, chalao, search, time, date.",
            hotwords="AGE stop okey okay ruko chup chrome edge vscode word excel powerpoint paint notepad calculator downloads desktop documents youtube volume awaz brightness roshni kholo chalao band karo",
        )

        text_parts = [segment.text.strip() for segment in segments]
        transcript = " ".join(part for part in text_parts if part).strip()
        latency = time.perf_counter() - t_start

        logger.info(
            "STT Transcribed '%s' in %.3fs (Audio duration: %.2fs)",
            transcript,
            latency,
            info.duration,
        )
        return transcript
