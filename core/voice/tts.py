"""Piper Text-to-Speech engine.

Security Rule 7:
Audio stays in memory only, never saved to disk.
"""

import time
from collections.abc import Callable
from pathlib import Path

import numpy as np
import sounddevice as sd
from piper import PiperVoice

from core.logger import get_logger

logger = get_logger("voice.tts")


URDU_INDICATORS = {
    "aap", "tum", "main", "mera", "meri", "hum", "kya", "hai", "hain", "hoon",
    "nahi", "theek", "kaise", "kaisa", "batao", "suno", "shukriya", "acha",
    "bohot", "yeh", "woh", "kar", "karna", "raha", "rahi", "din", "baat",
    "dost", "salaam", "assalam", "khuda", "hafiz", "alvida", "chahiye", "karo",
    "karen", "kaisi", "kaun", "kab", "kahan", "kyun", "wala", "wali", "wale",
    "ji", "guzra", "shamil", "paas", "sirf", "zaroorat", "lagbhag", "unka", "unki",
}


def is_urdu_text(text: str) -> bool:
    """Check if text contains Roman Urdu or Perso-Arabic script characters."""
    if any(ord(c) > 127 for c in text):
        return True
    words = {w.lower().strip(".,!?:;'\"-()") for w in text.split()}
    return bool(words & URDU_INDICATORS)


class TextToSpeech:
    """Hybrid Text-to-Speech using natural Urdu Neural TTS with Piper ONNX fallback."""

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

    def _synthesize_urdu_edge(self, text: str) -> tuple[np.ndarray, int] | None:
        """Synthesize authentic Pakistani Urdu speech using Microsoft Uzma Neural."""
        try:
            import asyncio
            import edge_tts
            import miniaudio

            async def _run():
                comm = edge_tts.Communicate(text.strip(), "ur-PK-UzmaNeural")
                buf = bytearray()
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        buf.extend(chunk["data"])
                return bytes(buf)

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        audio_bytes = pool.submit(lambda: asyncio.run(_run())).result(timeout=12.0)
                else:
                    audio_bytes = loop.run_until_complete(_run())
            except RuntimeError:
                audio_bytes = asyncio.run(_run())

            if not audio_bytes:
                return None

            decoded = miniaudio.decode(audio_bytes)
            raw = np.array(decoded.samples, dtype=np.int16)
            if decoded.nchannels > 1:
                mono = raw.reshape(-1, decoded.nchannels).mean(axis=1).astype(np.int16)
            else:
                mono = raw
            return mono, decoded.sample_rate

        except Exception as e:
            logger.debug("Edge TTS natural Urdu synthesis skipped: %s", e)
            return None

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        """Synthesize text into in-memory int16 PCM audio array.

        Args:
            text: Text to speak.

        Returns:
            Tuple of (audio_array, sample_rate).
        """
        if not text or not text.strip():
            return np.array([], dtype=np.int16), 22050

        # If text is Roman Urdu or Urdu, synthesize with natural Pakistani Urdu voice
        if is_urdu_text(text):
            edge_res = self._synthesize_urdu_edge(text)
            if edge_res is not None:
                return edge_res

        audio_pieces: list[np.ndarray] = []
        sample_rate = 22050

        for chunk in self._voice.synthesize(text.strip()):
            audio_pieces.append(chunk.audio_int16_array)
            sample_rate = chunk.sample_rate

        if not audio_pieces:
            return np.array([], dtype=np.int16), sample_rate

        combined = np.concatenate(audio_pieces)
        return combined, sample_rate

    def stop(self) -> None:
        """Immediately stop any active speech playback."""
        try:
            sd.stop()
        except sd.PortAudioError as e:
            logger.debug("PortAudio error while stopping playback: %s", e)

    def speak(
        self,
        text: str,
        interrupt_check: Callable[[], bool] | None = None,
    ) -> bool:
        """Synthesize and immediately play speech through sounddevice.

        Args:
            text: Text response to speak.
            interrupt_check: Optional callable that returns True to abort playback immediately.

        Returns:
            True if playback finished completely, False if interrupted.
        """
        if not text or not text.strip():
            return True

        t_start = time.perf_counter()
        audio_array, sr = self.synthesize(text)
        synth_latency = time.perf_counter() - t_start

        if len(audio_array) == 0:
            return True

        duration_sec = len(audio_array) / sr
        logger.info(
            "TTS Synthesized '%s' in %.3fs (Audio duration: %.2fs)",
            text[:50],
            synth_latency,
            duration_sec,
        )

        t_play = time.perf_counter()
        try:
            sd.play(audio_array, samplerate=sr)
            while True:
                stream = sd.get_stream()
                if stream is None or not stream.active:
                    break
                if interrupt_check and interrupt_check():
                    logger.info("TTS playback stopped on user interruption.")
                    sd.stop()
                    return False
                time.sleep(0.03)
            play_latency = time.perf_counter() - t_play
            logger.info("TTS playback completed in %.3fs", play_latency)
            return True
        except (sd.PortAudioError, RuntimeError, OSError) as e:
            logger.warning("Playback error: %s", e)
            self.stop()
            return False
