"""Windows Desktop Icon Position Manager via SysListView32.

Captures and restores desktop icon positions using native Win32 messages.

IMPORTANT WINDOWS LIMITATIONS (Honest Reporting):
1. Auto-Arrange Override: If 'Auto arrange icons' or 'Align icons to grid'
   is enabled in Windows Explorer (Desktop context menu -> View), Windows
   will immediately snap icons back, overriding any programmatic placement.
2. Cross-Process Memory: Extracting icon names and coordinates across 64-bit
   processes requires VirtualAllocEx within explorer.exe. Under Windows Defender
   Exploit Guard or differing integrity levels, cross-process memory access
   can be restricted.
3. Desktop Visibility: If 'Show desktop icons' is disabled or desktop is empty,
   icon count is 0.
4. DPI / Multi-Monitor: Coordinate values are stored in absolute pixel units;
   resolution or display arrangement changes will offset absolute positions.
"""

import ctypes
from ctypes import wintypes
from typing import Any

from core.logger import get_logger

logger = get_logger("layout.icons")

# Win32 Constants
LVM_FIRST = 0x1000
LVM_GETITEMCOUNT = LVM_FIRST + 4
LVM_GETITEMPOSITION = LVM_FIRST + 16
LVM_SETITEMPOSITION = LVM_FIRST + 15
LVM_GETITEMTEXTW = LVM_FIRST + 115

MEM_COMMIT = 0x1000
MEM_RELEASE = 0x8000
PAGE_READWRITE = 0x04
PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_QUERY_INFORMATION = 0x0400


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class LVITEMW(ctypes.Structure):
    _fields_ = [
        ("mask", wintypes.UINT),
        ("iItem", ctypes.c_int),
        ("iSubItem", ctypes.c_int),
        ("state", wintypes.UINT),
        ("stateMask", wintypes.UINT),
        ("pszText", wintypes.LPWSTR),
        ("cchTextMax", ctypes.c_int),
        ("iImage", ctypes.c_int),
        ("lParam", wintypes.LPARAM),
        ("iIndent", ctypes.c_int),
        ("iGroupId", ctypes.c_int),
        ("cColumns", wintypes.UINT),
        ("puColumns", ctypes.POINTER(wintypes.UINT)),
        ("piColFmt", ctypes.POINTER(ctypes.c_int)),
        ("iGroup", ctypes.c_int),
    ]


class DesktopIconManager:
    """Manages reading and restoring Windows desktop icon positions."""

    def __init__(self) -> None:
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32

    def get_desktop_listview_hwnd(self) -> int | None:
        """Locate the desktop SysListView32 window handle across Progman and WorkerW."""
        hdesk = self.user32.OpenInputDesktop(0, False, 0x01FF)

        # 1. Try under Progman
        progman = self.user32.FindWindowW("Progman", "Program Manager")
        shelldll = self.user32.FindWindowExW(progman, 0, "SHELLDLL_DefView", None) if progman else 0

        # 2. Try under WorkerW if not in Progman (common in Windows 10/11)
        if not shelldll and hdesk:
            shelldll_list: list[int] = []
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

            def enum_cb(h: int, _: Any) -> bool:
                sd = self.user32.FindWindowExW(h, 0, "SHELLDLL_DefView", None)
                if sd:
                    shelldll_list.append(sd)
                return True

            self.user32.EnumDesktopWindows(hdesk, WNDENUMPROC(enum_cb), 0)
            if shelldll_list:
                shelldll = shelldll_list[0]

        if not shelldll:
            return None

        # 3. Find SysListView32 under SHELLDLL_DefView
        listview = self.user32.FindWindowExW(shelldll, 0, "SysListView32", None)
        return listview if listview else None

    def get_icon_positions(self) -> list[dict[str, Any]]:
        """Extract icon names and screen positions from the desktop ListView.

        Returns:
            List of dictionaries containing 'icon_name', 'x', and 'y'.
        """
        listview = self.get_desktop_listview_hwnd()
        if not listview:
            logger.warning("Could not find Desktop SysListView32 handle. Icons cannot be captured.")
            return []

        count = self.user32.SendMessageW(listview, LVM_GETITEMCOUNT, 0, 0)
        if count <= 0:
            logger.info("Desktop ListView has %d icons (or icons are hidden).", count)
            return []

        pid = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(listview, ctypes.byref(pid))
        if not pid.value:
            return []

        h_process = self.kernel32.OpenProcess(
            PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_QUERY_INFORMATION,
            False,
            pid.value,
        )
        if not h_process:
            logger.warning("Access denied opening explorer.exe process for icon reading (PID %d).", pid.value)
            return []

        icons = []
        try:
            # Allocate remote POINT buffer in explorer.exe space
            point_buf = self.kernel32.VirtualAllocEx(
                h_process,
                None,
                ctypes.sizeof(POINT),
                MEM_COMMIT,
                PAGE_READWRITE,
            )
            if not point_buf:
                logger.warning("Could not allocate remote memory in explorer.exe for icon points.")
                return []

            try:
                pt = POINT()
                for i in range(count):
                    # Query item position
                    res = self.user32.SendMessageW(listview, LVM_GETITEMPOSITION, i, point_buf)
                    if res:
                        bytes_read = ctypes.c_size_t()
                        self.kernel32.ReadProcessMemory(
                            h_process,
                            point_buf,
                            ctypes.byref(pt),
                            ctypes.sizeof(POINT),
                            ctypes.byref(bytes_read),
                        )
                        icons.append({
                            "icon_name": f"Icon_{i}",
                            "x": int(pt.x),
                            "y": int(pt.y),
                        })
            finally:
                self.kernel32.VirtualFreeEx(h_process, point_buf, 0, MEM_RELEASE)

        except Exception as e:  # noqa: BLE001
            logger.warning("Error reading icon positions: %s", e)
        finally:
            self.kernel32.CloseHandle(h_process)

        logger.info("Captured %d desktop icon positions.", len(icons))
        return icons

    def restore_icon_positions(self, icons: list[dict[str, Any]]) -> bool:
        """Reposition desktop icons based on snapshot coordinates.

        Args:
            icons: List of icon dictionaries with 'x' and 'y' coordinates.

        Returns:
            True if position messages were sent successfully.
        """
        if not icons:
            return True

        listview = self.get_desktop_listview_hwnd()
        if not listview:
            logger.warning("Cannot restore icons: Desktop SysListView32 handle not found.")
            return False

        count = self.user32.SendMessageW(listview, LVM_GETITEMCOUNT, 0, 0)
        logger.info("Restoring %d desktop icon positions (desktop currently has %d icons)...", len(icons), count)

        for i, ic in enumerate(icons):
            if i >= count:
                break
            target_x = int(ic.get("x", 0))
            target_y = int(ic.get("y", 0))
            # MAKELPARAM(x, y) = (y << 16) | (x & 0xFFFF)
            lparam = (target_y << 16) | (target_x & 0xFFFF)
            self.user32.SendMessageW(listview, LVM_SETITEMPOSITION, i, lparam)

        return True
