"""In-memory microphone capture using sounddevice.

Security Rule 7:
Audio stays in memory only, never saved to disk.
"""

import queue
import threading

import numpy as np
import sounddevice as sd

from core.logger import get_logger

logger = get_logger("voice.audio_capture")


class AudioCapture:
    """Captures mono 16 kHz audio into in-memory ring buffers."""

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_size: int = 512,
        channels: int = 1,
    ) -> None:
        """Initialize AudioCapture.

        Args:
            sample_rate: Audio sampling frequency in Hz (default 16000).
            frame_size: Number of frames per block (default 512 = 32ms at 16kHz).
            channels: Number of audio channels (1 = mono).
        """
        self.sample_rate = sample_rate
        self.frame_size = frame_size
        self.channels = channels
        self._buffer: queue.Queue[np.ndarray] = queue.Queue(maxsize=100)
        self._stream: sd.InputStream | None = None
        self._is_running = False
        self._lock = threading.Lock()

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: dict,
        status: sd.CallbackFlags,
    ) -> None:
        """Callback invoked by PortAudio for each recorded audio block."""
        if status:
            logger.warning("Microphone stream status flag: %s", status)

        # Copy data to in-memory queue, drop oldest frame if full to prevent unbounded memory growth
        frame_copy = indata.copy().flatten()
        try:
            self._buffer.put_nowait(frame_copy)
        except queue.Full:
            try:
                self._buffer.get_nowait()
                self._buffer.put_nowait(frame_copy)
            except queue.Empty:
                pass

    def start(self) -> None:
        """Start microphone audio stream in background."""
        with self._lock:
            if self._is_running:
                return

            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                blocksize=self.frame_size,
                channels=self.channels,
                dtype="int16",
                callback=self._audio_callback,
            )
            self._stream.start()
            self._is_running = True
            logger.info("Microphone stream started at %d Hz, frame_size=%d", self.sample_rate, self.frame_size)

    def stop(self) -> None:
        """Stop microphone audio stream and drain in-memory buffer."""
        with self._lock:
            if not self._is_running:
                return

            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None

            self._is_running = False
            # Drain queue
            while not self._buffer.empty():
                try:
                    self._buffer.get_nowait()
                except queue.Empty:
                    break

            logger.info("Microphone stream stopped.")

    def read_frame(self, timeout: float = 1.0) -> np.ndarray | None:
        """Read a single PCM int16 audio frame from the in-memory queue.

        Args:
            timeout: Seconds to wait for next frame before returning None.

        Returns:
            np.ndarray of shape (frame_size,) with dtype int16, or None on timeout.
        """
        try:
            return self._buffer.get(timeout=timeout)
        except queue.Empty:
            return None

    @property
    def is_active(self) -> bool:
        """Whether the microphone is currently capturing."""
        return self._is_running
