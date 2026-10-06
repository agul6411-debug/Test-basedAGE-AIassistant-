"""Tests for safe process execution and allowlist enforcement."""

import sys

import pytest

from core.safety.process_runner import ProcessSecurityError, SafeProcessRunner


def test_run_command_success():
    res = SafeProcessRunner.run_command([sys.executable, "-c", "print('safe_output')"])
    assert res.returncode == 0
    assert "safe_output" in res.stdout


def test_run_command_rejects_string():
    with pytest.raises(ProcessSecurityError):
        # Must be a list, never a string
        SafeProcessRunner.run_command("python -c print(1)")  # type: ignore


def test_run_command_rejects_empty():
    with pytest.raises(ProcessSecurityError):
        SafeProcessRunner.run_command([])


def test_launch_allowlisted_app_success(monkeypatch):
    allowlist = {"test_tool": sys.executable}
    # Launch safe python command
    proc = SafeProcessRunner.launch_allowlisted_app("test_tool", allowlist, extra_args=["-c", "exit(0)"])
    proc.wait(timeout=5)
    assert proc.returncode == 0


def test_launch_allowlisted_app_rejects_unlisted():
    allowlist = {"notepad": "notepad.exe"}
    with pytest.raises(ProcessSecurityError):
        SafeProcessRunner.launch_allowlisted_app("malicious_app", allowlist)
