"""Piper Text-to-Speech engine.

Security Rule 7:
Audio stays in memory only, never saved to disk.
"""

import time
from pathlib import Path

import numpy as np
import sounddevice as sd
from piper import PiperVoice

from core.logger import get_logger

logger = get_logger("voice.tts")


class TextToSpeech:
    """Offline Text-to-Speech using Piper ONNX."""

    def __init__(
        self,
        model_path: str | Path | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        """Initialize Piper TTS voice.

        Args:
            model_path: Path to en_US-lessac-medium.onnx. Defaults to models/en_US-lessac-medium.onnx.
            config_path: Path to .onnx.json config file.
        """
        model = Path(model_path) if model_path else Path("models/en_US-lessac-medium.onnx")
        config = Path(config_path) if config_path else Path("models/en_US-lessac-medium.onnx.json")

        if not model.exists() or not config.exists():
            raise FileNotFoundError(f"Piper model or config not found at {model}. Run model downloader first.")

        logger.info("Loading Piper TTS voice from %s...", model)
        t0 = time.perf_counter()
        self._voice = PiperVoice.load(str(model), config_path=str(config))
        load_time = time.perf_counter() - t0
        logger.info("Piper TTS voice loaded in %.2f seconds.", load_time)

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        """Synthesize text into in-memory int16 PCM audio array.

        Args:
            text: Text to speak.

        Returns:
            Tuple of (audio_array, sample_rate).
        """
        if not text or not text.strip():
            return np.array([], dtype=np.int16), 22050

        audio_pieces: list[np.ndarray] = []
        sample_rate = 22050

        for chunk in self._voice.synthesize(text.strip()):
            audio_pieces.append(chunk.audio_int16_array)
            sample_rate = chunk.sample_rate

        if not audio_pieces:
            return np.array([], dtype=np.int16), sample_rate

        combined = np.concatenate(audio_pieces)
        return combined, sample_rate

    def speak(self, text: str) -> None:
        """Synthesize and immediately play speech through sounddevice.

        Args:
            text: Text response to speak.
        """
        if not text or not text.strip():
            return

        t_start = time.perf_counter()
        audio_array, sr = self.synthesize(text)
        synth_latency = time.perf_counter() - t_start

        if len(audio_array) == 0:
            return

        duration_sec = len(audio_array) / sr
        logger.info(
            "TTS Synthesized '%s' in %.3fs (Audio duration: %.2fs)",
            text[:50],
            synth_latency,
            duration_sec,
        )

        t_play = time.perf_counter()
        sd.play(audio_array, samplerate=sr)
        sd.wait()
        play_latency = time.perf_counter() - t_play

        logger.info("TTS playback completed in %.3fs", play_latency)
