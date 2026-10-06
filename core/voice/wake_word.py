"""Porcupine wake-word detection engine with hotkey fallback.

Security Rule 6:
Secrets (e.g. Porcupine access key) live in .env only.
Never hardcode or log secrets.
"""

import os
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

from core.logger import get_logger

logger = get_logger("voice.wake_word")

# Load environment variables from .env
load_dotenv()


class WakeWordDetector:
    """Detects wake words using Picovoice Porcupine with automatic hotkey fallback."""

    def __init__(
        self,
        keyword: str = "Hey AGE",
        custom_model_path: str | Path | None = None,
        sensitivities: float = 0.5,
    ) -> None:
        """Initialize Porcupine wake word detector.

        Args:
            keyword: Wake word phrase (e.g., "Hey AGE").
            custom_model_path: Optional path to custom .ppn file.
            sensitivities: Sensitivity threshold (0.0 to 1.0).
        """
        self.keyword = keyword
        self.sensitivities = sensitivities
        self.access_key = os.getenv("PORCUPINE_ACCESS_KEY", "").strip()
        self._porcupine = None
        self._is_ready = False
        self._init_engine(custom_model_path)

    def _init_engine(self, custom_model_path: str | Path | None) -> None:
        """Initialize Porcupine engine or flag fallback mode."""
        if not self.access_key or self.access_key.lower().startswith("your_porcupine"):
            logger.warning(
                "Porcupine access key not found or unset in .env; "
                "falling back to Ctrl+Space hotkey only."
            )
            return

        try:
            import pvporcupine

            ppn_file = Path(custom_model_path) if custom_model_path else Path("models/hey_age_windows.ppn")

            if ppn_file.exists():
                logger.info("Loading custom Porcupine model from %s", ppn_file)
                self._porcupine = pvporcupine.create(
                    access_key=self.access_key,
                    keyword_paths=[str(ppn_file)],
                    sensitivities=[self.sensitivities],
                )
            else:
                # Built-in fallback keyword if custom ppn is not provided
                builtin_kw = "jarvis" if "jarvis" in pvporcupine.KEYWORDS else "porcupine"
                logger.info(
                    "Custom 'Hey AGE' model not found at %s. Using built-in keyword '%s'.",
                    ppn_file,
                    builtin_kw,
                )
                self._porcupine = pvporcupine.create(
                    access_key=self.access_key,
                    keywords=[builtin_kw],
                    sensitivities=[self.sensitivities],
                )

            self._is_ready = True
            logger.info("Porcupine wake word detector initialized successfully.")

        except Exception as e:  # noqa: BLE001
            logger.warning(
                "Failed to initialize Porcupine (%s); falling back to Ctrl+Space hotkey only.",
                e,
            )
            self._porcupine = None
            self._is_ready = False

    @property
    def is_available(self) -> bool:
        """Whether Porcupine wake word detection is active."""
        return self._is_ready and self._porcupine is not None

    @property
    def frame_length(self) -> int:
        """Required number of audio samples per frame (usually 512)."""
        return self._porcupine.frame_length if self._porcupine else 512

    @property
    def sample_rate(self) -> int:
        """Required audio sample rate (16000 Hz)."""
        return self._porcupine.sample_rate if self._porcupine else 16000

    def process_frame(self, pcm_frame: np.ndarray) -> bool:
        """Process a single PCM int16 frame.

        Args:
            pcm_frame: 1D array of 512 int16 samples.

        Returns:
            True if wake word was detected in this frame, False otherwise.
        """
        if not self.is_available:
            return False

        try:
            # Ensure correct format for Porcupine
            if len(pcm_frame) != self.frame_length:
                return False
            result = self._porcupine.process(pcm_frame.tolist())
            return result >= 0
        except Exception as e:  # noqa: BLE001
            logger.error("Error processing audio frame in Porcupine: %s", e)
            return False

    def close(self) -> None:
        """Clean up Porcupine native resources."""
        if self._porcupine:
            self._porcupine.delete()
            self._porcupine = None
            self._is_ready = False
