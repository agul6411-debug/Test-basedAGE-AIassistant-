"""Unit tests for Desktop Layout Manager, Autostart, and Layout Tools.

Security Rules Tested:
- Rule 2: Subprocess argument lists without shell=True for schtasks.
- Rule 4: Relaunches ONLY allowlisted apps, ignores unapproved apps.
- Rule 5: Destructive / restorative actions require user confirmation.
- Rule 9: Task Scheduler runs as normal user without admin elevation.
- Rule 13: Layout database stored strictly within data/.
- Invariant: Never kills or modifies existing processes during restore.
- Invariant: Never touches user files during restore.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.brain.router import CommandRouter
from core.layout.autosave import LayoutAutoSaver
from core.layout.autostart import AutostartManager
from core.layout.db import LayoutDB
from core.layout.icon_manager import DesktopIconManager
from core.layout.window_manager import WindowManager
from core.safety.base import SecurityException
from core.safety.confirmation import ConfirmationManager
from core.tools.registry import registry
from core.tools.restore_layout import RestoreLayoutTool
from core.tools.save_layout import SaveLayoutTool

# ==============================================================================
# 1. LayoutDB Tests
# ==============================================================================

def test_layout_db_schema_and_insert(tmp_path: Path):
    db = LayoutDB(db_path="test_layout.db", base_dir=tmp_path)

    windows = [
        {
            "app_name": "notepad",
            "process_name": "notepad.exe",
            "title": "Untitled - Notepad",
            "x": 100,
            "y": 150,
            "width": 800,
            "height": 600,
            "state": "normal",
        }
    ]
    icons = [{"icon_name": "Recycle Bin", "x": 50, "y": 50}]

    snap_id = db.save_snapshot("manual", windows, icons, max_snapshots=10)
    assert snap_id > 0

    latest = db.get_latest_snapshot()
    assert latest is not None
    assert latest["id"] == snap_id
    assert latest["trigger_type"] == "manual"
    assert len(latest["windows"]) == 1
    assert latest["windows"][0]["app_name"] == "notepad"
    assert latest["windows"][0]["x"] == 100
    assert len(latest["icons"]) == 1
    assert latest["icons"][0]["icon_name"] == "Recycle Bin"


def test_layout_db_pruning_keeps_last_10(tmp_path: Path):
    db = LayoutDB(db_path="test_layout.db", base_dir=tmp_path)

    # Insert 15 snapshots with max_snapshots=10
    for i in range(15):
        db.save_snapshot(
            trigger_type="autosave",
            windows=[{"app_name": "calc", "process_name": "calc.exe", "title": f"Calc {i}", "x": i, "y": i, "width": 400, "height": 300, "state": "normal"}],
            icons=[{"icon_name": f"Icon_{i}", "x": i * 10, "y": i * 10}],
            max_snapshots=10,
        )

    snapshots = db.get_snapshots(limit=50)
    assert len(snapshots) == 10

    # Oldest retained snapshot should be ID 6, newest should be ID 15
    ids = [s["id"] for s in snapshots]
    assert min(ids) == 6
    assert max(ids) == 15

    # Verify foreign key cascade deleted pruned entries
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT snapshot_id) FROM window_entries;")
        distinct_windows = cursor.fetchone()[0]
        assert distinct_windows == 10

        cursor.execute("SELECT COUNT(DISTINCT snapshot_id) FROM icon_entries;")
        distinct_icons = cursor.fetchone()[0]
        assert distinct_icons == 10


def test_layout_db_path_confinement_security(tmp_path: Path):
    # Rule 13: database path must not escape data/
    with pytest.raises(SecurityException):
        LayoutDB(db_path="../../escaped.db", base_dir=tmp_path)


def test_layout_db_empty_snapshot(tmp_path: Path):
    db = LayoutDB(db_path="test_layout.db", base_dir=tmp_path)
    assert db.get_latest_snapshot() is None
    assert db.get_snapshots() == []


# ==============================================================================
# 2. DesktopIconManager Tests
# ==============================================================================

def test_icon_manager_handles_missing_listview():
    mgr = DesktopIconManager()
    with patch.object(mgr, "get_desktop_listview_hwnd", return_value=None):
        positions = mgr.get_icon_positions()
        assert positions == []

        res = mgr.restore_icon_positions([{"icon_name": "test", "x": 10, "y": 20}])
        assert res is False


def test_icon_manager_empty_restore():
    mgr = DesktopIconManager()
    assert mgr.restore_icon_positions([]) is True


def test_icon_manager_restore_sends_messages():
    mgr = DesktopIconManager()
    with patch.object(mgr, "get_desktop_listview_hwnd", return_value=12345):
        sent_messages = []

        def fake_send_message(hwnd, msg, wparam, lparam):
            sent_messages.append((hwnd, msg, wparam, lparam))
            if msg == 0x1004:  # LVM_GETITEMCOUNT
                return 5
            return 1

        with patch.object(mgr.user32, "SendMessageW", side_effect=fake_send_message):
            icons = [
                {"icon_name": "Icon_0", "x": 100, "y": 200},
                {"icon_name": "Icon_1", "x": 300, "y": 400},
            ]
            success = mgr.restore_icon_positions(icons)
            assert success is True
            # Should have called LVM_GETITEMCOUNT once and LVM_SETITEMPOSITION twice
            set_pos_msgs = [m for m in sent_messages if m[1] == 0x1000 + 15]
            assert len(set_pos_msgs) == 2
            # Check packed coordinates: (y << 16) | (x & 0xFFFF)
            expected_lparam_0 = (200 << 16) | (100 & 0xFFFF)
            assert set_pos_msgs[0][3] == expected_lparam_0


# ==============================================================================
# 3. WindowManager Tests
# ==============================================================================

def test_window_manager_get_open_windows():
    mgr = WindowManager()
    windows = mgr.get_open_windows()
    assert isinstance(windows, list)
    for w in windows:
        assert "hwnd" in w
        assert "title" in w
        assert "x" in w
        assert "y" in w
        assert "width" in w
        assert "height" in w
        assert "state" in w


def test_window_manager_restore_safety_invariant_allowlisted_only():
    mgr = WindowManager()

    saved_windows = [
        {"app_name": "notepad", "process_name": "notepad.exe", "title": "Notes", "x": 100, "y": 100, "width": 800, "height": 600, "state": "normal"},
        {"app_name": "unauthorized_malware", "process_name": "malware.exe", "title": "Evil", "x": 200, "y": 200, "width": 400, "height": 300, "state": "normal"},
    ]

    launched_apps = []
    with (
        patch("core.safety.process_runner.SafeProcessRunner.launch_allowlisted_app", side_effect=lambda app, allowlist: launched_apps.append(app)),
        patch.object(mgr, "get_open_windows", return_value=[]),
        patch.object(mgr.user32, "SetWindowPos", return_value=1),
        patch.object(mgr.user32, "ShowWindow", return_value=1),
        patch("psutil.process_iter", return_value=[]),
    ):
        summary = mgr.restore_windows(saved_windows)

    # Invariant: Relaunches ONLY allowlisted apps, NEVER unauthorized apps
    assert "notepad" in launched_apps
    assert "unauthorized_malware" not in launched_apps
    assert summary["relaunched_apps"] == ["notepad"]


def test_window_manager_restore_never_kills_processes():
    mgr = WindowManager()
    saved = [{"app_name": "calc", "process_name": "calc.exe", "title": "Calculator", "x": 50, "y": 50, "width": 300, "height": 400, "state": "normal"}]

    mock_proc = MagicMock()
    mock_proc.info = {"name": "calc.exe"}

    with (
        patch("psutil.process_iter", return_value=[mock_proc]),
        patch.object(mgr, "get_open_windows", return_value=[{"hwnd": 999, "app_name": "calc", "process_name": "calc.exe", "title": "Calculator"}]),
        patch.object(mgr.user32, "SetWindowPos", return_value=1) as mock_set_pos,
        patch.object(mgr.user32, "ShowWindow", return_value=1),
    ):
        summary = mgr.restore_windows(saved)

    # Invariant: Process must NOT be killed or terminated
    mock_proc.terminate.assert_not_called()
    mock_proc.kill.assert_not_called()
    assert summary["windows_positioned"] == 1
    mock_set_pos.assert_called_once()


# ==============================================================================
# 4. LayoutAutoSaver Tests
# ==============================================================================

def test_autosaver_capture_and_save(tmp_path: Path):
    db = LayoutDB(db_path="test_layout.db", base_dir=tmp_path)
    win_mgr = MagicMock()
    win_mgr.get_open_windows.return_value = [{"app_name": "notepad", "process_name": "notepad.exe", "title": "Notes", "x": 10, "y": 20, "width": 500, "height": 400, "state": "normal"}]
    icon_mgr = MagicMock()
    icon_mgr.get_icon_positions.return_value = [{"icon_name": "Icon_1", "x": 5, "y": 5}]

    saver = LayoutAutoSaver(db=db, window_mgr=win_mgr, icon_mgr=icon_mgr, interval_sec=300, max_snapshots=10)
    snap_id = saver.capture_and_save("manual")
    assert snap_id > 0

    latest = db.get_latest_snapshot()
    assert latest is not None
    assert latest["id"] == snap_id
    assert latest["trigger_type"] == "manual"


def test_autosaver_stop_captures_shutdown(tmp_path: Path):
    db = LayoutDB(db_path="test_layout.db", base_dir=tmp_path)
    win_mgr = MagicMock()
    win_mgr.get_open_windows.return_value = []
    icon_mgr = MagicMock()
    icon_mgr.get_icon_positions.return_value = []

    saver = LayoutAutoSaver(db=db, window_mgr=win_mgr, icon_mgr=icon_mgr, interval_sec=300, max_snapshots=10)
    saver.start()
    saver.stop(save_on_shutdown=True)

    latest = db.get_latest_snapshot()
    assert latest is not None
    assert latest["trigger_type"] == "shutdown"


# ==============================================================================
# 5. AutostartManager Tests (Task Scheduler as Normal User)
# ==============================================================================

def test_autostart_enable_uses_argument_list_and_normal_user():
    mgr = AutostartManager(task_name="Test_AGE")

    executed_cmds = []

    def fake_run(cmd, **kwargs):
        executed_cmds.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="SUCCESS", stderr="")

    with patch("core.safety.process_runner.SafeProcessRunner.run_command", side_effect=fake_run):
        ok = mgr.enable("demo_voice.py")
        assert ok is True

    assert len(executed_cmds) == 1
    cmd = executed_cmds[0]
    # Rule 2: Sequence of arguments, no shell=True
    assert isinstance(cmd, list)
    assert cmd[0] == "schtasks"
    assert "/create" in cmd
    assert "/tn" in cmd
    assert "Test_AGE" in cmd
    assert "/sc" in cmd
    assert "onlogon" in cmd
    # Rule 9: Does not request /ru SYSTEM or admin elevation
    assert "SYSTEM" not in cmd


def test_autostart_disable():
    mgr = AutostartManager(task_name="Test_AGE")
    executed_cmds = []

    def fake_run(cmd, **kwargs):
        executed_cmds.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("core.safety.process_runner.SafeProcessRunner.run_command", side_effect=fake_run):
        ok = mgr.disable()
        assert ok is True

    assert len(executed_cmds) == 1
    assert executed_cmds[0] == ["schtasks", "/delete", "/tn", "Test_AGE", "/f"]


def test_autostart_is_enabled():
    mgr = AutostartManager(task_name="Test_AGE")
    with patch("core.safety.process_runner.SafeProcessRunner.run_command") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="OK", stderr="")
        assert mgr.is_enabled() is True

        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="ERROR")
        assert mgr.is_enabled() is False


# ==============================================================================
# 6. Tools and Router Tests (Save / Restore Layout)
# ==============================================================================

def test_save_layout_tool_execution(tmp_path: Path):
    tool = registry.get("save_layout")
    assert tool is not None
    assert isinstance(tool, SaveLayoutTool)
    assert tool.is_dangerous is False

    with patch("core.layout.autosave.LayoutAutoSaver.capture_and_save", return_value=42):
        result = tool.run()
        assert result.success is True
        assert "Snapshot #42" in result.message
        assert result.data["snapshot_id"] == 42


def test_restore_layout_tool_metadata():
    tool = registry.get("restore_layout")
    assert tool is not None
    assert isinstance(tool, RestoreLayoutTool)
    # Rule 5: Restoring layout changes state and requires confirmation
    assert tool.is_dangerous is True


def test_restore_layout_tool_handles_no_snapshot():
    tool = registry.get("restore_layout")
    assert tool is not None
    with patch("core.layout.db.LayoutDB.get_latest_snapshot", return_value=None):
        result = tool.run()
        assert result.success is False
        assert "No desktop layout snapshot found" in result.message


def test_restore_layout_tool_successful_execution():
    tool = registry.get("restore_layout")
    assert tool is not None

    fake_snapshot = {
        "id": 7,
        "timestamp": "2026-10-06T12:00:00Z",
        "windows": [{"app_name": "notepad", "process_name": "notepad.exe", "title": "Notes", "x": 10, "y": 10, "width": 800, "height": 600, "state": "normal"}],
        "icons": [{"icon_name": "Icon_0", "x": 100, "y": 200}],
    }

    with (
        patch("core.layout.db.LayoutDB.get_latest_snapshot", return_value=fake_snapshot),
        patch("core.layout.window_manager.WindowManager.restore_windows", return_value={"relaunched_apps": ["notepad"], "windows_positioned": 1, "total_saved_windows": 1}),
        patch("core.layout.icon_manager.DesktopIconManager.restore_icon_positions", return_value=True),
    ):
        result = tool.run()
        assert result.success is True
        assert "Restored layout from snapshot #7" in result.message
        assert "Relaunched apps: notepad" in result.message


def test_router_save_desktop_execution():
    cm = ConfirmationManager()
    router = CommandRouter(confirmation_manager=cm, enable_llm_fallback=False)

    with patch("core.layout.autosave.LayoutAutoSaver.capture_and_save", return_value=1):
        res = router.execute_command("save my desktop")
        assert res.matched is True
        assert res.success is True
        assert res.tool_name == "save_layout"


def test_router_restore_desktop_requires_confirmation():
    cm = ConfirmationManager()
    router = CommandRouter(confirmation_manager=cm, enable_llm_fallback=False)

    # 1. When user denies confirmation -> action cancelled
    with patch.object(cm, "request_confirmation", return_value=False):
        res = router.execute_command("restore my desktop")
        assert res.matched is True
        assert res.success is False
        assert "cancelled" in res.message.lower()

    # 2. When user confirms -> action proceeds
    fake_snapshot = {
        "id": 99,
        "timestamp": "2026-10-06T12:00:00Z",
        "windows": [],
        "icons": [],
    }
    with (
        patch.object(cm, "request_confirmation", return_value=True),
        patch("core.layout.db.LayoutDB.get_latest_snapshot", return_value=fake_snapshot),
        patch("core.layout.window_manager.WindowManager.restore_windows", return_value={"relaunched_apps": [], "windows_positioned": 0, "total_saved_windows": 0}),
        patch("core.layout.icon_manager.DesktopIconManager.restore_icon_positions", return_value=True),
    ):
        res = router.execute_command("restore my desktop")
        assert res.matched is True
        assert res.success is True
        assert res.tool_name == "restore_layout"

