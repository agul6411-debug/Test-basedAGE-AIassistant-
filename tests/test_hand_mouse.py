"""Unit tests for hand mouse One Euro filter, gesture detection, IPC, and controller."""

import math
from unittest.mock import MagicMock

import pytest

from core.hand_mouse_controller import HandMouseController
from core.safety.emergency_stop import EmergencyStop
from hand_mouse.filter import OneEuroFilter1D, OneEuroFilter2D
from hand_mouse.gestures import GestureAction, GestureDetector
from hand_mouse.ipc import HandMouseIPCServer, send_hand_mouse_command


class MockLandmark:
    """Mock MediaPipe hand landmark."""
    def __init__(self, x: float = 0.5, y: float = 0.5, z: float = 0.0) -> None:
        self.x = x
        self.y = y
        self.z = z


def create_neutral_hand(index_x: float = 0.5, index_y: float = 0.5) -> list[MockLandmark]:
    """Create a default 21-landmark hand."""
    landmarks = [MockLandmark(0.5, 0.8, 0.0) for _ in range(21)]
    # Set index tip
    landmarks[GestureDetector.INDEX_TIP] = MockLandmark(index_x, index_y, 0.0)
    # Set thumb tip away from index
    landmarks[GestureDetector.THUMB_TIP] = MockLandmark(index_x + 0.2, index_y, 0.0)
    # Set joints for curled fingers
    landmarks[GestureDetector.INDEX_PIP] = MockLandmark(index_x, index_y + 0.1, 0.0)
    landmarks[GestureDetector.MIDDLE_PIP] = MockLandmark(0.5, 0.6, 0.0)
    landmarks[GestureDetector.MIDDLE_TIP] = MockLandmark(0.5, 0.7, 0.0)  # Curled
    landmarks[GestureDetector.RING_PIP] = MockLandmark(0.5, 0.6, 0.0)
    landmarks[GestureDetector.RING_TIP] = MockLandmark(0.5, 0.7, 0.0)
    landmarks[GestureDetector.PINKY_PIP] = MockLandmark(0.5, 0.6, 0.0)
    landmarks[GestureDetector.PINKY_TIP] = MockLandmark(0.5, 0.7, 0.0)
    return landmarks


# ==============================================================================
# One Euro Filter Tests
# ==============================================================================

def test_one_euro_filter_initialization():
    f1d = OneEuroFilter1D(freq=30.0, min_cutoff=1.0, beta=0.007)
    val = f1d.filter(100.0, timestamp=0.0)
    assert val == 100.0


def test_one_euro_filter_jitter_reduction():
    f2d = OneEuroFilter2D(freq=30.0, min_cutoff=1.0, beta=0.007)
    base_x = 500.0
    base_y = 500.0

    filtered_positions = []
    # Feed stationary point with high frequency jitter (+- 5 px)
    for i in range(30):
        t = i * (1.0 / 30.0)
        noise = 5.0 * (1.0 if i % 2 == 0 else -1.0)
        fx, fy = f2d.filter(base_x + noise, base_y + noise, timestamp=t)
        filtered_positions.append((fx, fy))

    # Later filtered values should stay very close to 500
    last_x, last_y = filtered_positions[-1]
    assert abs(last_x - base_x) < 2.5
    assert abs(last_y - base_y) < 2.5


def test_one_euro_filter_reset():
    f2d = OneEuroFilter2D()
    f2d.filter(100.0, 100.0, timestamp=1.0)
    f2d.reset()
    assert f2d.x_filter._last_time is None


# ==============================================================================
# Gesture Detector Tests
# ==============================================================================

def test_coordinate_mapping_and_mirroring():
    detector = GestureDetector(
        screen_width=1920,
        screen_height=1080,
        active_region=(0.2, 0.8, 0.2, 0.8),
    )

    # Center of active region in camera (0.5, 0.5)
    # Mirrored x = 1.0 - 0.5 = 0.5
    sx, sy = detector._map_to_screen(0.5, 0.5)
    assert math.isclose(sx, 1919 / 2.0, abs_tol=5.0)
    assert math.isclose(sy, 1079 / 2.0, abs_tol=5.0)

    # Moving hand to user's right (camera x decreases from 0.5 to 0.3)
    # Mirrored x increases to 0.7 -> screen x should increase!
    sx_right, _ = detector._map_to_screen(0.3, 0.5)
    assert sx_right > sx


def test_pinch_click_gesture():
    detector = GestureDetector(pinch_threshold=0.055, drag_delay_sec=0.3)
    hand = create_neutral_hand(index_x=0.5, index_y=0.5)

    # Frame 1: Hand neutral, no pinch
    ev1 = detector.process_landmarks(hand, timestamp=1.0)
    assert ev1.action == GestureAction.MOVE

    # Frame 2: Thumb and index pinch together (distance < 0.055)
    hand[GestureDetector.THUMB_TIP] = MockLandmark(0.51, 0.51, 0.0)
    ev2 = detector.process_landmarks(hand, timestamp=1.05)
    assert ev2.action == GestureAction.MOVE

    # Frame 3: Pinch released after 0.1s (< drag_delay_sec 0.3s)
    hand[GestureDetector.THUMB_TIP] = MockLandmark(0.65, 0.5, 0.0)
    ev3 = detector.process_landmarks(hand, timestamp=1.15)
    assert ev3.action == GestureAction.CLICK


def test_index_finger_tap_click_gesture():
    detector = GestureDetector(drag_delay_sec=0.3)
    hand = create_neutral_hand(index_x=0.5, index_y=0.5)

    # Frame 1: Hand neutral, index extended (pointing)
    ev1 = detector.process_landmarks(hand, timestamp=1.0)
    assert ev1.action == GestureAction.MOVE

    # Frame 2: Index finger bends down (tip dips to y=0.65, below pip at 0.6)
    hand[GestureDetector.INDEX_TIP] = MockLandmark(0.5, 0.65, 0.0)
    ev2 = detector.process_landmarks(hand, timestamp=1.05)
    assert ev2.action == GestureAction.MOVE

    # Frame 3: Index finger straightens back up (release to click)
    hand[GestureDetector.INDEX_TIP] = MockLandmark(0.5, 0.5, 0.0)
    ev3 = detector.process_landmarks(hand, timestamp=1.15)
    assert ev3.action == GestureAction.CLICK


def test_hold_pinch_drag_gesture():
    detector = GestureDetector(pinch_threshold=0.055, drag_delay_sec=0.3)
    hand = create_neutral_hand(index_x=0.5, index_y=0.5)

    # Frame 1: Pinch start at t=1.0
    hand[GestureDetector.THUMB_TIP] = MockLandmark(0.51, 0.51, 0.0)
    detector.process_landmarks(hand, timestamp=1.0)

    # Frame 2: Pinch held past drag delay (t=1.35s)
    ev_drag = detector.process_landmarks(hand, timestamp=1.35)
    assert ev_drag.action == GestureAction.MOUSE_DOWN
    assert ev_drag.is_dragging is True

    # Frame 3: Released
    hand[GestureDetector.THUMB_TIP] = MockLandmark(0.65, 0.5, 0.0)
    ev_release = detector.process_landmarks(hand, timestamp=1.4)
    assert ev_release.action == GestureAction.MOUSE_UP
    assert ev_release.is_dragging is False


def test_two_finger_scroll():
    detector = GestureDetector()
    hand = create_neutral_hand(index_x=0.5, index_y=0.5)

    # Make index and middle finger both point UP (tips above PIP joints)
    hand[GestureDetector.INDEX_TIP] = MockLandmark(0.48, 0.3, 0.0)
    hand[GestureDetector.INDEX_PIP] = MockLandmark(0.48, 0.45, 0.0)
    hand[GestureDetector.MIDDLE_TIP] = MockLandmark(0.52, 0.3, 0.0)
    hand[GestureDetector.MIDDLE_PIP] = MockLandmark(0.52, 0.45, 0.0)
    # Ring and pinky curled
    hand[GestureDetector.RING_TIP] = MockLandmark(0.56, 0.6, 0.0)
    hand[GestureDetector.RING_PIP] = MockLandmark(0.56, 0.5, 0.0)
    hand[GestureDetector.PINKY_TIP] = MockLandmark(0.6, 0.6, 0.0)
    hand[GestureDetector.PINKY_PIP] = MockLandmark(0.6, 0.5, 0.0)

    # Frame 1: Establish baseline scroll position
    detector.process_landmarks(hand, timestamp=1.0)

    # Frame 2: Move fingers UP to y=0.25 (dy = -0.05 -> scroll UP)
    hand[GestureDetector.INDEX_TIP] = MockLandmark(0.48, 0.25, 0.0)
    hand[GestureDetector.MIDDLE_TIP] = MockLandmark(0.52, 0.25, 0.0)
    ev_scroll = detector.process_landmarks(hand, timestamp=1.05)

    assert ev_scroll.action == GestureAction.SCROLL
    assert ev_scroll.scroll_amount > 0


def test_dead_zone_suppression_during_pinch():
    detector = GestureDetector(dead_zone_px=10.0, pinch_threshold=0.055)
    hand = create_neutral_hand(index_x=0.5, index_y=0.5)

    # Start pinch
    hand[GestureDetector.THUMB_TIP] = MockLandmark(0.51, 0.51, 0.0)
    ev1 = detector.process_landmarks(hand, timestamp=1.0)
    pos1 = (ev1.cursor_x, ev1.cursor_y)

    # Tiny movement while pinching (< 10 px)
    hand[GestureDetector.INDEX_TIP] = MockLandmark(0.5005, 0.5005, 0.0)
    ev2 = detector.process_landmarks(hand, timestamp=1.05)
    pos2 = (ev2.cursor_x, ev2.cursor_y)

    # Dead zone should hold cursor in place
    assert pos1 == pos2


# ==============================================================================
# Security & IPC Tests
# ==============================================================================

def test_ipc_server_rejects_external_host():
    with pytest.raises(ValueError, match="SECURITY VIOLATION"):
        HandMouseIPCServer(host="0.0.0.0")  # nosec: B104


def test_ipc_server_authentication(monkeypatch):
    server = HandMouseIPCServer(port=18766)
    server.start()

    try:
        # 1. Invalid token -> Rejected
        monkeypatch.setattr("hand_mouse.ipc.verify_token", lambda tok: tok == "valid_token")
        bad_resp = send_hand_mouse_command("STATUS", token="wrong_token", port=18766)
        assert bad_resp["success"] is False
        assert "Unauthorized" in bad_resp["error"]

        # 2. Valid token -> Accepted
        good_resp = send_hand_mouse_command("STATUS", token="valid_token", port=18766)
        assert good_resp["success"] is True
    finally:
        server.stop()


# ==============================================================================
# Controller Tests
# ==============================================================================

def test_controller_emergency_stop_integration():
    stop = EmergencyStop()
    controller = HandMouseController(emergency_stop=stop)

    # Mock running process
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    controller._process = mock_proc

    # Triggering emergency stop should stop the controller
    stop.trigger()
    assert controller._process is None
    mock_proc.terminate.assert_called_once()
