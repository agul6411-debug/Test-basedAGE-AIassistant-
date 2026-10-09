"""Standalone Hand Mouse Process Runner.

Started and stopped by the core.
Executes OpenCV capture, MediaPipe Hand tracking, One Euro smoothing, and mouse control.

Security Rule 7: Camera frames processed in RAM only, never saved to disk.
Security Rule 10: Instant emergency-stop hotkey (Ctrl+Shift+Esc).
Security Rule 11: Visible on-screen indicator while camera is active.
"""

import ctypes
import signal
import sys
import time
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
from pynput import keyboard
from pynput.mouse import Button
from pynput.mouse import Controller as MouseController

from core.config import load_config
from core.logger import setup_logger
from hand_mouse.camera import CameraCapture
from hand_mouse.gestures import GestureAction, GestureDetector
from hand_mouse.ipc import HandMouseIPCServer

logger = setup_logger("hand_mouse.log", log_level="INFO")


def get_screen_resolution() -> tuple[int, int]:
    """Get primary display dimensions using native Windows user32 API."""
    try:
        w = ctypes.windll.user32.GetSystemMetrics(0)
        h = ctypes.windll.user32.GetSystemMetrics(1)
        if w > 0 and h > 0:
            return (w, h)
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not query user32 screen metrics: %s", e)
    return (1920, 1080)


class HandMouseApp:
    """Manages the lifecycle and execution loop of the hand mouse subsystem."""

    def __init__(self) -> None:
        self.config = load_config()
        self.mouse = MouseController()
        screen_w, screen_h = get_screen_resolution()

        hm_cfg = self.config.hand_mouse
        reg = hm_cfg.active_region
        active_region_tuple = (reg.x_min, reg.x_max, reg.y_min, reg.y_max)

        self.detector = GestureDetector(
            screen_width=screen_w,
            screen_height=screen_h,
            active_region=active_region_tuple,
            dead_zone_px=hm_cfg.dead_zone_px,
            pinch_threshold=hm_cfg.pinch_threshold,
            drag_delay_sec=hm_cfg.drag_delay_sec,
            filter_min_cutoff=hm_cfg.smoothing.min_cutoff,
            filter_beta=hm_cfg.smoothing.beta,
        )

        res_w = getattr(hm_cfg.resolution, "width", 640) if hasattr(hm_cfg, "resolution") else 640
        res_h = getattr(hm_cfg.resolution, "height", 480) if hasattr(hm_cfg, "resolution") else 480
        self.camera = CameraCapture(
            camera_index=hm_cfg.camera_index,
            resolution=(res_w, res_h),
            fps_limit=hm_cfg.fps_limit,
        )

        self.missing_hand_timeout = hm_cfg.missing_hand_timeout_sec
        self._running = False
        self._paused = False
        self._is_dragging = False
        self._last_hand_time = time.time()
        self._hotkey_listener: keyboard.GlobalHotKeys | None = None

        # IPC Server for core process communication
        self.ipc_server = HandMouseIPCServer(
            host=hm_cfg.ipc_host,
            port=hm_cfg.ipc_port,
            command_handler=self._handle_ipc_command,
        )

    def _handle_ipc_command(self, cmd: str) -> dict[str, Any]:
        """Process verified commands received over local authenticated IPC."""
        clean_cmd = cmd.strip().upper()
        if clean_cmd == "STOP":
            logger.info("Received STOP command via authenticated IPC.")
            self.stop()
            return {"success": True, "message": "Hand mouse stopping"}
        if clean_cmd == "PAUSE":
            self._paused = True
            return {"success": True, "message": "Hand mouse paused"}
        if clean_cmd == "RESUME":
            self._paused = False
            self._last_hand_time = time.time()
            return {"success": True, "message": "Hand mouse resumed"}
        if clean_cmd == "STATUS":
            hand_seen = (time.time() - self._last_hand_time) < 2.0
            return {
                "success": True,
                "running": self._running,
                "paused": self._paused,
                "hand_detected": hand_seen,
            }
        return {"success": False, "error": f"Unknown command '{cmd}'"}

    def _start_emergency_hotkey(self) -> None:
        """Security Rule 10: Register Ctrl+Shift+Esc emergency stop."""
        try:
            self._hotkey_listener = keyboard.GlobalHotKeys({
                "<ctrl>+<shift>+<esc>": self._emergency_stop_triggered
            })
            self._hotkey_listener.daemon = True
            self._hotkey_listener.start()
            logger.info("Emergency-stop hotkey (<ctrl>+<shift>+<esc>) registered.")
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to register emergency stop hotkey: %s", e)

    def _emergency_stop_triggered(self) -> None:
        """Triggered immediately when Ctrl+Shift+Esc is pressed."""
        logger.critical("EMERGENCY STOP TRIGGERED VIA HOTKEY! Stopping hand mouse.")
        self.stop()

    def stop(self) -> None:
        """Stop processing, release mouse, and shut down camera."""
        self._running = False
        if self._is_dragging:
            try:
                self.mouse.release(Button.left)
            except Exception as e:  # noqa: BLE001
                logger.debug("Error releasing mouse button: %s", e)
            self._is_dragging = False

        self.camera.release()
        self.ipc_server.stop()
        if self._hotkey_listener:
            try:
                self._hotkey_listener.stop()
            except Exception as e:  # noqa: BLE001
                logger.debug("Error stopping hotkey listener: %s", e)
            self._hotkey_listener = None

        try:
            cv2.destroyAllWindows()
        except Exception as e:  # noqa: BLE001
            logger.debug("Error destroying CV windows: %s", e)

    def run(self) -> None:
        """Main execution loop for hand tracking and mouse dispatch."""
        logger.info("Starting AGE Hand Mouse Subprocess...")
        if not self.camera.start():
            logger.error("Cannot start hand mouse: Camera not accessible.")
            return

        self._start_emergency_hotkey()
        self.ipc_server.start()
        self._running = True
        self._last_hand_time = time.time()

        # Initialize MediaPipe Hands detector (supports MediaPipe Tasks and legacy solutions)
        model_path = Path(__file__).resolve().parent.parent / "models" / "hand_landmarker.task"
        use_tasks_api = not hasattr(mp, "solutions")

        if use_tasks_api:
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision

            base_options = mp_python.BaseOptions(model_asset_path=str(model_path))
            options = vision.HandLandmarkerOptions(
                base_options=base_options,
                num_hands=1,
                min_hand_detection_confidence=0.7,
                min_tracking_confidence=0.7,
                running_mode=vision.RunningMode.IMAGE,
            )
            hands_detector = vision.HandLandmarker.create_from_options(options)
        else:
            mp_hands = mp.solutions.hands
            hands_detector = mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                min_detection_confidence=0.7,
                min_tracking_confidence=0.7,
            )

        window_name = "AGE Camera Indicator - Hand Mouse"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 560, 420)
        cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)

        try:
            while self._running:
                frame_rgb = self.camera.read_frame()
                if frame_rgb is None:
                    time.sleep(0.01)
                    continue

                now = time.time()
                # Run hand landmark inference (memory-only buffer)
                landmarks = None
                if use_tasks_api:
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
                    results = hands_detector.detect(mp_image)
                    hand_found = bool(results.hand_landmarks and len(results.hand_landmarks) > 0)
                    if hand_found:
                        landmarks = results.hand_landmarks[0]
                else:
                    results = hands_detector.process(frame_rgb)
                    hand_found = results.multi_hand_landmarks is not None and len(results.multi_hand_landmarks) > 0
                    if hand_found:
                        landmarks = results.multi_hand_landmarks[0].landmark

                if hand_found:
                    self._last_hand_time = now
                    if self._paused:
                        self._paused = False
                        logger.info("Hand detected again. Resuming tracking.")

                # Automatic stop/pause if hand missing for 10 seconds
                missing_duration = now - self._last_hand_time
                if missing_duration > self.missing_hand_timeout and not self._paused:
                    logger.info("Hand missing for %.1fs. Entering auto-pause state.", missing_duration)
                    self._paused = True
                    if self._is_dragging:
                        self.mouse.release(Button.left)
                        self._is_dragging = False
                    self.detector.reset()

                # Process gestures if active and not paused
                is_pinching = False
                if hand_found and not self._paused and landmarks is not None:
                    event = self.detector.process_landmarks(landmarks, timestamp=now)
                    is_pinching = getattr(event, "is_pinching", False)
                    self._dispatch_gesture_event(event)
                elif not hand_found:
                    self.detector.reset()

                # Security Rule 11: Render visible on-screen camera indicator
                self._render_indicator(
                    window_name,
                    frame_rgb,
                    hand_found,
                    self._paused,
                    landmarks=landmarks if hand_found else None,
                    is_pinching=is_pinching,
                    is_dragging=self._is_dragging,
                )

                # Check GUI window events
                key = cv2.waitKey(1) & 0xFF
                if key == 27:  # ESC key closes
                    logger.info("ESC key pressed in indicator window.")
                    break

        except KeyboardInterrupt:
            logger.info("Hand mouse interrupted by user.")
        finally:
            hands_detector.close()
            self.stop()
            logger.info("AGE Hand Mouse Subprocess exited cleanly.")

    def _dispatch_gesture_event(self, event: Any) -> None:
        """Send simulated input commands via pynput."""
        action = event.action

        if action == GestureAction.MOVE:
            self.mouse.position = (event.cursor_x, event.cursor_y)

        elif action == GestureAction.CLICK:
            self.mouse.position = (event.cursor_x, event.cursor_y)
            self.mouse.click(Button.left)
            logger.info("Left click executed at (%d, %d)", event.cursor_x, event.cursor_y)

        elif action == GestureAction.MOUSE_DOWN:
            self.mouse.position = (event.cursor_x, event.cursor_y)
            self.mouse.press(Button.left)
            self._is_dragging = True
            logger.debug("Drag started at (%d, %d)", event.cursor_x, event.cursor_y)

        elif action == GestureAction.MOUSE_UP:
            self.mouse.position = (event.cursor_x, event.cursor_y)
            self.mouse.release(Button.left)
            self._is_dragging = False
            logger.debug("Drag released at (%d, %d)", event.cursor_x, event.cursor_y)

        elif action == GestureAction.SCROLL and event.scroll_amount != 0:
            self.mouse.scroll(0, event.scroll_amount)
            logger.debug("Scroll %d dispatched", event.scroll_amount)

    def _render_indicator(
        self,
        window_name: str,
        frame_rgb: Any,
        hand_detected: bool,
        is_paused: bool,
        landmarks: Any = None,
        is_pinching: bool = False,
        is_dragging: bool = False,
    ) -> None:
        """Render compact visible preview with on-screen camera on/off indicator."""
        # Convert RGB back to BGR for OpenCV display
        bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

        # Render visible desktop status widget at 560x420
        preview = cv2.resize(bgr, (560, 420))
        prev_h, prev_w = preview.shape[:2]

        # Draw landmark fingertips if available
        if landmarks is not None and len(landmarks) >= 21:
            try:
                thumb = landmarks[4]
                index_pip = landmarks[6]
                index = landmarks[8]
                tx, ty = int(thumb.x * prev_w), int(thumb.y * prev_h)
                ix, iy = int(index.x * prev_w), int(index.y * prev_h)
                px, py = int(index_pip.x * prev_w), int(index_pip.y * prev_h)

                # Bone line index joint to tip
                cv2.line(preview, (px, py), (ix, iy), (220, 220, 220), 2)
                cv2.circle(preview, (px, py), 4, (180, 180, 180), -1)

                # Line between thumb and index
                line_col = (0, 255, 255) if is_pinching else (120, 120, 120)
                cv2.line(preview, (tx, ty), (ix, iy), line_col, 2)

                # Colored fingertip indicators
                index_col = (0, 255, 255) if is_pinching else (0, 255, 0)
                cv2.circle(preview, (tx, ty), 7, (0, 180, 255), -1)
                cv2.circle(preview, (ix, iy), 7, index_col, -1)
            except Exception as e:  # noqa: BLE001
                logger.debug("Fingertip preview overlay error: %s", e)

        # Status text & color
        if is_paused:
            color = (0, 165, 255)  # Amber / Orange
            status_text = "[PAUSED - HAND MISSING]"
        elif is_dragging:
            color = (255, 0, 255)  # Magenta
            status_text = "[DRAGGING - MOVE HAND]"
        elif is_pinching:
            color = (0, 255, 255)  # Cyan
            status_text = "[CLICK DETECTED - STRAIGHTEN TO CLICK]"
        elif hand_detected:
            color = (0, 255, 0)    # Green
            status_text = "[INDEX POINTING - MOVING MOUSE]"
        else:
            color = (0, 200, 200)  # Yellow
            status_text = "[CAMERA ACTIVE - SEARCHING FOR HAND]"

        # Draw status banner
        cv2.rectangle(preview, (0, 0), (560, 34), (20, 20, 20), -1)
        cv2.circle(preview, (16, 17), 8, color, -1)
        cv2.putText(
            preview,
            status_text,
            (32, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            color,
            1,
            cv2.LINE_AA,
        )

        cv2.imshow(window_name, preview)


def main() -> None:
    """Subprocess main entrypoint."""
    # Setup signal handlers
    def sig_handler(signum: int, frame: Any) -> None:
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    app = HandMouseApp()
    app.run()


if __name__ == "__main__":
    main()
