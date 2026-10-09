"""Voice Activity Detection (VAD) using Silero VAD ONNX.

Detects voice presence and accurately determines end-of-speech silence.
"""

from pathlib import Path

import numpy as np
import onnxruntime as ort

from core.logger import get_logger

logger = get_logger("voice.vad")


class SileroVAD:
    """Silero VAD ONNX model wrapper for 16 kHz audio."""

    def __init__(self, model_path: str | Path | None = None) -> None:
        """Initialize Silero VAD ONNX session.

        Args:
            model_path: Path to silero_vad.onnx. Defaults to models/silero_vad.onnx.
        """
        path = Path(model_path) if model_path else Path("models/silero_vad.onnx")
        if not path.exists():
            raise FileNotFoundError(f"Silero VAD model not found at {path}. Run model downloader first.")

        # CPU inference options
        session_options = ort.SessionOptions()
        session_options.inter_op_num_threads = 1
        session_options.intra_op_num_threads = 1

        self._session = ort.InferenceSession(str(path), session_options, providers=["CPUExecutionProvider"])
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._tail = np.zeros(64, dtype=np.float32)
        self._sr = np.array(16000, dtype=np.int64)
        logger.info("Silero VAD initialized on CPU from %s", path)

    def reset(self) -> None:
        """Reset internal recurrent state and rolling context tail."""
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._tail = np.zeros(64, dtype=np.float32)

    def process_frame(self, pcm_frame: np.ndarray) -> float:
        """Process 512 samples (32ms at 16kHz) and return speech probability.

        Args:
            pcm_frame: int16 array of 512 samples.

        Returns:
            Speech probability between 0.0 and 1.0.
        """
        if len(pcm_frame) != 512:
            raise ValueError(f"Silero VAD expects 512 samples per frame, received {len(pcm_frame)}")

        # Convert int16 PCM to normalized float32 [-1.0, 1.0]
        if pcm_frame.dtype == np.int16:
            audio_float = (pcm_frame.astype(np.float32) / 32768.0)
        else:
            audio_float = pcm_frame.astype(np.float32)

        # Silero VAD v5 requires 576 samples: 64 samples rolling context + 512 frame samples
        input_tensor = np.concatenate([self._tail, audio_float]).reshape(1, 576).astype(np.float32)
        self._tail = audio_float[-64:].copy()

        inputs = {
            "input": input_tensor,
            "state": self._state,
            "sr": self._sr,
        }

        out, self._state = self._session.run(None, inputs)
        return float(out[0][0])

    def is_speech(self, pcm_frame: np.ndarray, threshold: float = 0.5) -> bool:
        """Check whether frame contains active speech."""
        return self.process_frame(pcm_frame) >= threshold


class SpeechEndpointDetector:
    """Detects start of speech and end-of-speech silence cutoff."""

    def __init__(
        self,
        vad: SileroVAD | None = None,
        speech_threshold: float = 0.38,
        silence_duration_sec: float = 1.2,
        max_duration_sec: float = 15.0,
        sample_rate: int = 16000,
        frame_size: int = 512,
    ) -> None:
        """Initialize endpoint detector.

        Args:
            vad: Optional SileroVAD instance.
            speech_threshold: Probability threshold to classify speech.
            silence_duration_sec: Continuous silence after speech to end recording.
            max_duration_sec: Maximum total duration before forced stop.
            sample_rate: Audio sampling frequency in Hz.
            frame_size: Samples per frame.
        """
        self.vad = vad or SileroVAD()
        self.speech_threshold = speech_threshold
        self.silence_duration_sec = silence_duration_sec
        self.max_duration_sec = max_duration_sec
        self.sample_rate = sample_rate
        self.frame_size = frame_size

        # Duration of one frame in seconds (512 / 16000 = 0.032s)
        self.frame_duration = frame_size / sample_rate
        self.silence_frame_limit = int(self.silence_duration_sec / self.frame_duration)
        self.max_frame_limit = int(self.max_duration_sec / self.frame_duration)

    def record_until_silence(
        self,
        frame_generator,
        initial_frames: list[np.ndarray] | None = None,
        speech_already_started: bool = False,
    ) -> np.ndarray:
        """Consume frames from generator until speech begins and finishes.

        Args:
            frame_generator: Generator yielding 512-sample PCM int16 frames.
            initial_frames: Optional audio frames recorded before trigger to prepend.
            speech_already_started: Whether speech onset was already detected.

        Returns:
            Concatenated in-memory 1D int16 NumPy array of spoken audio.
        """
        self.vad.reset()
        recorded_frames: list[np.ndarray] = list(initial_frames) if initial_frames else []
        speech_started = speech_already_started or (len(recorded_frames) > 0)
        consecutive_silence_frames = 0
        total_frames = len(recorded_frames)

        for frame in frame_generator:
            if frame is None or len(frame) != self.frame_size:
                continue

            prob = self.vad.process_frame(frame)
            is_speaking = prob >= self.speech_threshold
            recorded_frames.append(frame)
            total_frames += 1

            if not speech_started:
                if is_speaking:
                    speech_started = True
                    consecutive_silence_frames = 0
                    logger.debug("Speech onset detected (prob=%.3f)", prob)
                else:
                    # Keep rolling history of last 15 frames (~480ms pre-roll)
                    if len(recorded_frames) > 15:
                        recorded_frames.pop(0)
                    # If nobody spoke within 5.0s after listening started, time out early
                    if total_frames >= int(5.0 / self.frame_duration):
                        logger.info("Speech onset timeout reached (5.0s).")
                        break
            else:
                if is_speaking:
                    consecutive_silence_frames = 0
                else:
                    consecutive_silence_frames += 1
                    if consecutive_silence_frames >= self.silence_frame_limit:
                        logger.debug("End of speech detected after %.2fs silence", self.silence_duration_sec)
                        break

            if total_frames >= self.max_frame_limit:
                logger.info("Maximum speech recording limit reached (%.1fs)", self.max_duration_sec)
                break

        if not speech_started or not recorded_frames:
            return np.array([], dtype=np.int16)

        return np.concatenate(recorded_frames)
