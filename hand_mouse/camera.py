"""OpenCV Camera capture wrapper with in-memory frame buffering and rate limiting.

Security Rule 7: Never store raw camera frames on disk. Process strictly in RAM.
"""

import time

import cv2
import numpy as np

from core.logger import get_logger

logger = get_logger("hand_mouse.camera")


class CameraCapture:
    """Manages OpenCV webcam video stream with rate limiting."""

    def __init__(
        self,
        camera_index: int = 0,
        resolution: tuple[int, int] = (640, 480),
        fps_limit: int = 30,
    ) -> None:
        """Initialize CameraCapture.

        Args:
            camera_index: Hardware device index (default: 0).
            resolution: (width, height) resolution tuple (default: 640x480).
            fps_limit: Target frames per second cap.
        """
        self.camera_index = camera_index
        self.width, self.height = resolution
        self.fps_limit = max(1, fps_limit)
        self.frame_interval = 1.0 / self.fps_limit

        self._cap: cv2.VideoCapture | None = None
        self._last_frame_time: float = 0.0

    def start(self) -> bool:
        """Open camera device and configure resolution."""
        if self._cap is not None and self._cap.isOpened():
            return True

        logger.info("Opening camera device %d (%dx%d)...", self.camera_index, self.width, self.height)
        # Prefer CAP_DSHOW on Windows for fast device initialization
        self._cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        if not self._cap.isOpened():
            # Fallback to default backend
            self._cap = cv2.VideoCapture(self.camera_index)

        if not self._cap.isOpened():
            logger.error("Failed to open camera device %d.", self.camera_index)
            self._cap = None
            return False

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps_limit)

        actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info("Camera device %d active at %dx%d.", self.camera_index, actual_w, actual_h)
        return True

    def read_frame(self) -> np.ndarray | None:
        """Read a single frame with rate limiting.

        Frames are maintained exclusively in memory as NumPy ndarrays.

        Returns:
            RGB NumPy array or None if frame grab fails.
        """
        if self._cap is None or not self._cap.isOpened():
            return None

        # Rate limiting to target FPS
        now = time.perf_counter()
        elapsed = now - self._last_frame_time
        if elapsed < self.frame_interval:
            time.sleep(self.frame_interval - elapsed)
        self._last_frame_time = time.perf_counter()

        ret, frame_bgr = self._cap.read()
        if not ret or frame_bgr is None:
            return None

        # Return RGB frame for MediaPipe (in-memory only)
        return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

    def is_active(self) -> bool:
        """Check if camera capture is currently open."""
        return self._cap is not None and self._cap.isOpened()

    def release(self) -> None:
        """Release camera hardware resource."""
        if self._cap is not None:
            logger.info("Releasing camera device %d.", self.camera_index)
            self._cap.release()
            self._cap = None
