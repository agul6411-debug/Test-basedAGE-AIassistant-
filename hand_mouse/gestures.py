"""Hand landmark gesture detector and screen coordinate mapper.

Security Rule 7: Landmark processing occurs strictly in memory.
Security Rule 9: Normal user permissions only.
"""

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any

from hand_mouse.filter import OneEuroFilter2D


class GestureAction(Enum):
    """Actions emitted by gesture detector."""
    NONE = "none"
    MOVE = "move"
    CLICK = "click"
    MOUSE_DOWN = "mouse_down"  # Drag start
    MOUSE_UP = "mouse_up"      # Drag release
    SCROLL = "scroll"


@dataclass
class GestureEvent:
    """Event produced by gesture analysis."""
    action: GestureAction
    cursor_x: int = 0
    cursor_y: int = 0
    scroll_amount: int = 0
    is_dragging: bool = False


class GestureDetector:
    """Analyzes hand landmarks and generates smoothed mouse control events."""

    # Landmark indices for MediaPipe Hands
    WRIST = 0
    THUMB_TIP = 4
    INDEX_MCP = 5
    INDEX_PIP = 6
    INDEX_DIP = 7
    INDEX_TIP = 8
    MIDDLE_MCP = 9
    MIDDLE_PIP = 10
    MIDDLE_DIP = 11
    MIDDLE_TIP = 12
    RING_PIP = 14
    RING_TIP = 16
    PINKY_PIP = 18
    PINKY_TIP = 20

    def __init__(
        self,
        screen_width: int = 1920,
        screen_height: int = 1080,
        active_region: tuple[float, float, float, float] = (0.2, 0.8, 0.2, 0.8),
        dead_zone_px: float = 6.0,
        pinch_threshold: float = 0.055,
        drag_delay_sec: float = 0.3,
        filter_min_cutoff: float = 1.0,
        filter_beta: float = 0.007,
    ) -> None:
        """Initialize GestureDetector.

        Args:
            screen_width: Primary display width in pixels.
            screen_height: Primary display height in pixels.
            active_region: Normalized (x_min, x_max, y_min, y_max) camera region.
            dead_zone_px: Movement threshold below which cursor does not drift during clicks.
            pinch_threshold: Normalized distance threshold for thumb-index pinch.
            drag_delay_sec: Duration pinch must be held to initiate drag.
            filter_min_cutoff: One Euro filter minimum cutoff frequency.
            filter_beta: One Euro filter velocity adaptation coefficient.
        """
        self.screen_width = max(100, screen_width)
        self.screen_height = max(100, screen_height)
        self.x_min, self.x_max, self.y_min, self.y_max = active_region
        self.dead_zone_px = dead_zone_px
        self.pinch_threshold = pinch_threshold
        self.drag_delay_sec = drag_delay_sec

        self.filter = OneEuroFilter2D(
            freq=30.0,
            min_cutoff=filter_min_cutoff,
            beta=filter_beta,
        )

        self._last_cursor_x: float = screen_width / 2.0
        self._last_cursor_y: float = screen_height / 2.0
        self._is_pinched: bool = False
        self._is_dragging: bool = False
        self._pinch_start_time: float = 0.0
        self._last_scroll_y: float | None = None

    def _euclidean_dist(self, p1: Any, p2: Any) -> float:
        """Calculate Euclidean distance between two landmarks."""
        dx = p1.x - p2.x
        dy = p1.y - p2.y
        dz = getattr(p1, "z", 0.0) - getattr(p2, "z", 0.0)
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def _map_to_screen(self, norm_x: float, norm_y: float) -> tuple[float, float]:
        """Map camera normalized coordinates to desktop screen resolution with horizontal mirror."""
        # Mirror horizontally so moving user hand to the right moves pointer right
        mirrored_x = 1.0 - norm_x

        # Normalize within active region
        dx = max(0.001, self.x_max - self.x_min)
        dy = max(0.001, self.y_max - self.y_min)

        clamped_x = max(0.0, min(1.0, (mirrored_x - self.x_min) / dx))
        clamped_y = max(0.0, min(1.0, (norm_y - self.y_min) / dy))

        screen_x = clamped_x * (self.screen_width - 1)
        screen_y = clamped_y * (self.screen_height - 1)
        return (screen_x, screen_y)

    def process_landmarks(
        self,
        landmarks: list[Any],
        timestamp: float,
    ) -> GestureEvent:
        """Process detected hand landmarks and return gesture event.

        Args:
            landmarks: List of 21 MediaPipe hand landmarks.
            timestamp: Monotonic timestamp in seconds.

        Returns:
            GestureEvent object.
        """
        if not landmarks or len(landmarks) < 21:
            return GestureEvent(action=GestureAction.NONE)

        index_tip = landmarks[self.INDEX_TIP]
        thumb_tip = landmarks[self.THUMB_TIP]
        middle_tip = landmarks[self.MIDDLE_TIP]
        index_pip = landmarks[self.INDEX_PIP]
        middle_pip = landmarks[self.MIDDLE_PIP]
        ring_pip = landmarks[self.RING_PIP]
        ring_tip = landmarks[self.RING_TIP]
        pinky_pip = landmarks[self.PINKY_PIP]
        pinky_tip = landmarks[self.PINKY_TIP]

        # 1. Coordinate Mapping & Smoothing
        raw_sx, raw_sy = self._map_to_screen(index_tip.x, index_tip.y)
        smoothed_x, smoothed_y = self.filter.filter(raw_sx, raw_sy, timestamp)

        # Apply dead zone against previous position
        dist_from_prev = math.hypot(smoothed_x - self._last_cursor_x, smoothed_y - self._last_cursor_y)
        if dist_from_prev >= self.dead_zone_px or not self._is_pinched:
            target_x = smoothed_x
            target_y = smoothed_y
            self._last_cursor_x = smoothed_x
            self._last_cursor_y = smoothed_y
        else:
            # Within dead zone during pinch: hold previous position
            target_x = self._last_cursor_x
            target_y = self._last_cursor_y

        cur_x = round(max(0, min(self.screen_width - 1, target_x)))
        cur_y = round(max(0, min(self.screen_height - 1, target_y)))

        # 2. Check for Two-Finger Scroll
        # Both index and middle fingers extended; ring and pinky curled
        index_up = index_tip.y < index_pip.y
        middle_up = middle_tip.y < middle_pip.y
        ring_curled = ring_tip.y > ring_pip.y
        pinky_curled = pinky_tip.y > pinky_pip.y
        two_fingers_close = abs(index_tip.x - middle_tip.x) < 0.08

        pinch_dist = self._euclidean_dist(thumb_tip, index_tip)
        is_pinching = pinch_dist < self.pinch_threshold

        if index_up and middle_up and ring_curled and pinky_curled and two_fingers_close and not is_pinching:
            avg_y = (index_tip.y + middle_tip.y) / 2.0
            scroll_amt = 0
            if self._last_scroll_y is not None:
                dy = avg_y - self._last_scroll_y
                if abs(dy) > 0.015:
                    # Moving fingers UP (smaller y) scrolls UP (+), DOWN scrolls DOWN (-)
                    scroll_amt = int(-dy * 120.0)
            self._last_scroll_y = avg_y

            # Reset any pinch state
            if self._is_dragging:
                self._is_dragging = False
                return GestureEvent(action=GestureAction.MOUSE_UP, cursor_x=cur_x, cursor_y=cur_y)
            self._is_pinched = False

            if scroll_amt != 0:
                return GestureEvent(
                    action=GestureAction.SCROLL,
                    cursor_x=cur_x,
                    cursor_y=cur_y,
                    scroll_amount=scroll_amt,
                )
            return GestureEvent(action=GestureAction.MOVE, cursor_x=cur_x, cursor_y=cur_y)

        self._last_scroll_y = None

        # 3. Pinch & Drag State Machine
        if is_pinching:
            if not self._is_pinched:
                # Pinch started
                self._is_pinched = True
                self._pinch_start_time = timestamp
                return GestureEvent(action=GestureAction.MOVE, cursor_x=cur_x, cursor_y=cur_y)

            # Already pinching - check drag threshold
            pinch_duration = timestamp - self._pinch_start_time
            if pinch_duration >= self.drag_delay_sec and not self._is_dragging:
                self._is_dragging = True
                return GestureEvent(
                    action=GestureAction.MOUSE_DOWN,
                    cursor_x=cur_x,
                    cursor_y=cur_y,
                    is_dragging=True,
                )

            return GestureEvent(
                action=GestureAction.MOVE,
                cursor_x=cur_x,
                cursor_y=cur_y,
                is_dragging=self._is_dragging,
            )

        # Not pinching
        if self._is_pinched:
            self._is_pinched = False
            if self._is_dragging:
                self._is_dragging = False
                return GestureEvent(action=GestureAction.MOUSE_UP, cursor_x=cur_x, cursor_y=cur_y)

            # Short pinch released: Click!
            return GestureEvent(action=GestureAction.CLICK, cursor_x=cur_x, cursor_y=cur_y)

        return GestureEvent(action=GestureAction.MOVE, cursor_x=cur_x, cursor_y=cur_y)

    def reset(self) -> None:
        """Reset state machine and filter on hand lost."""
        self.filter.reset()
        self._is_pinched = False
        self._is_dragging = False
        self._last_scroll_y = None
