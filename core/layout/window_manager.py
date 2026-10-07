"""Windows Desktop Window State Capture and Restoration.

Security Rule 4: Relaunches ONLY allowlisted apps from config.yaml.
Security Invariant: Never kills or modifies processes during restore.
Security Invariant: Never touches files during restore.
"""

import ctypes
import time
from ctypes import wintypes
from typing import Any

import psutil

from core.config import load_config
from core.logger import get_logger
from core.safety.process_runner import SafeProcessRunner

logger = get_logger("layout.windows")

# Win32 Constants
SW_SHOWNORMAL = 1
SW_SHOWMINIMIZED = 2
SW_SHOWMAXIMIZED = 3
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.UINT),
        ("flags", wintypes.UINT),
        ("showCmd", wintypes.UINT),
        ("ptMinPosition", wintypes.POINT),
        ("ptMaxPosition", wintypes.POINT),
        ("rcNormalPosition", RECT),
    ]


class WindowManager:
    """Captures open window properties and safely positions allowlisted applications."""

    def __init__(self) -> None:
        self.user32 = ctypes.windll.user32

    def get_open_windows(self) -> list[dict[str, Any]]:
        """Enumerate interactive visible top-level windows.

        Returns:
            List of window dictionaries containing title, process_name, coords, and state.
        """
        windows: list[dict[str, Any]] = []
        hdesk = self.user32.OpenInputDesktop(0, False, 0x01FF)

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def enum_cb(hwnd: int, _: Any) -> bool:
            # Must be a visible window
            if not self.user32.IsWindowVisible(hwnd):
                return True

            # Must have a non-empty window title
            length = self.user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True

            buff = ctypes.create_unicode_buffer(length + 1)
            self.user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value.strip()
            if not title:
                return True

            # Filter out background system windows
            cls_buff = ctypes.create_unicode_buffer(256)
            self.user32.GetClassNameW(hwnd, cls_buff, 256)
            cls_name = cls_buff.value
            if cls_name in ("Progman", "Shell_TrayWnd", "WorkerW", "Windows.UI.Core.CoreWindow"):
                return True

            # Get PID and process name
            pid = wintypes.DWORD()
            self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            proc_name = ""
            if pid.value > 0:
                try:
                    proc_name = psutil.Process(pid.value).name().lower()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    proc_name = "unknown"

            # Query window coordinates
            rc = RECT()
            self.user32.GetWindowRect(hwnd, ctypes.byref(rc))
            w = rc.right - rc.left
            h = rc.bottom - rc.top

            # Query window state (normal, maximized, minimized)
            placement = WINDOWPLACEMENT()
            placement.length = ctypes.sizeof(WINDOWPLACEMENT)
            self.user32.GetWindowPlacement(hwnd, ctypes.byref(placement))

            state = "normal"
            if placement.showCmd == SW_SHOWMAXIMIZED:
                state = "maximized"
            elif placement.showCmd == SW_SHOWMINIMIZED:
                state = "minimized"

            # Check if matching an allowlist alias
            config = load_config()
            app_alias = ""
            for alias, exe_path in config.safety.app_allowlist.items():
                if proc_name == exe_path.lower() or proc_name == f"{alias}.exe":
                    app_alias = alias
                    break

            windows.append({
                "hwnd": hwnd,
                "title": title,
                "process_name": proc_name,
                "app_name": app_alias,
                "x": int(rc.left),
                "y": int(rc.top),
                "width": int(w),
                "height": int(h),
                "state": state,
            })
            return True

        if hdesk:
            self.user32.EnumDesktopWindows(hdesk, WNDENUMPROC(enum_cb), 0)
        else:
            self.user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

        logger.info("Captured %d open desktop windows.", len(windows))
        return windows

    def restore_windows(self, saved_windows: list[dict[str, Any]]) -> dict[str, Any]:
        """Restore saved window placements.

        Security Rules:
        - Relaunches ONLY allowlisted apps (Rule 4).
        - Never kills or modifies existing processes.
        - Never touches user files.

        Args:
            saved_windows: List of window dictionaries from a snapshot.

        Returns:
            Dict summary of relaunched apps and positioned windows.
        """
        config = load_config()
        allowlist = config.safety.app_allowlist
        relaunched: list[str] = []
        positioned: int = 0

        # 1. Identify which allowlisted apps were saved in snapshot
        apps_to_relaunch: set[str] = set()
        for w in saved_windows:
            app_name = w.get("app_name", "").strip().lower()
            if app_name and app_name in allowlist:
                apps_to_relaunch.add(app_name)
            else:
                # Also check process name against allowlist
                proc_name = w.get("process_name", "").strip().lower()
                for alias, exe in allowlist.items():
                    if proc_name == exe.lower() or proc_name == f"{alias}.exe":
                        apps_to_relaunch.add(alias)

        # 2. Check currently running allowlisted processes
        current_running_apps: set[str] = set()
        for proc in psutil.process_iter(attrs=["name"]):
            try:
                pname = (proc.info.get("name") or "").lower()
                for alias, exe in allowlist.items():
                    if pname == exe.lower() or pname == f"{alias}.exe":
                        current_running_apps.add(alias)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # 3. Relaunch missing allowlisted apps ONLY
        for app in apps_to_relaunch:
            if app not in current_running_apps:
                try:
                    logger.info("Relaunching allowlisted app '%s' for layout restoration...", app)
                    SafeProcessRunner.launch_allowlisted_app(app, allowlist)
                    relaunched.append(app)
                except Exception as e:  # noqa: BLE001
                    logger.error("Failed to relaunch allowlisted app '%s': %s", app, e)

        # Brief delay to allow newly launched windows to materialize
        if relaunched:
            time.sleep(1.5)

        # 4. Position open windows matching saved entries
        current_windows = self.get_open_windows()

        for saved in saved_windows:
            s_app = saved.get("app_name", "").lower()
            s_proc = saved.get("process_name", "").lower()
            s_title = saved.get("title", "").lower()

            target_hwnd: int | None = None
            # Find best matching current window by app/proc and title
            for curr in current_windows:
                c_app = curr.get("app_name", "").lower()
                c_proc = curr.get("process_name", "").lower()
                c_title = curr.get("title", "").lower()

                if ((s_app and s_app == c_app) or (s_proc and s_proc == c_proc)) and (
                    s_title in c_title or c_title in s_title or not s_title
                ):
                    target_hwnd = curr.get("hwnd")
                    break

            if target_hwnd:
                x = int(saved.get("x", 0))
                y = int(saved.get("y", 0))
                w = int(saved.get("width", 800))
                h = int(saved.get("height", 600))
                state = saved.get("state", "normal")

                # Reposition window
                self.user32.SetWindowPos(
                    target_hwnd,
                    0,
                    x,
                    y,
                    w,
                    h,
                    SWP_NOZORDER | SWP_NOACTIVATE | SWP_SHOWWINDOW,
                )

                # Set window state
                if state == "maximized":
                    self.user32.ShowWindow(target_hwnd, SW_SHOWMAXIMIZED)
                elif state == "minimized":
                    self.user32.ShowWindow(target_hwnd, SW_SHOWMINIMIZED)
                else:
                    self.user32.ShowWindow(target_hwnd, SW_SHOWNORMAL)

                positioned += 1

        return {
            "relaunched_apps": relaunched,
            "windows_positioned": positioned,
            "total_saved_windows": len(saved_windows),
        }
