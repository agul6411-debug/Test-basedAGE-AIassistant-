"""Safe subprocess execution guardrails.

Security Rule 2:
Never use shell=True, eval, exec, or os.system.
Use subprocess with an argument list.

Security Rule 4:
Apps can only be launched from an allowlist in config.yaml, never from arbitrary strings.
"""

# Safe wrapper layer strictly enforcing shell=False and argument lists
import os
import shutil
import subprocess  # nosec: B404
import sys
from collections.abc import Sequence
from pathlib import Path

from core.safety.base import SecurityException


class ProcessSecurityError(SecurityException):
    """Raised when process execution violates safety constraints."""


class SafeProcessRunner:
    """Enforces strict process spawning security rules."""

    @staticmethod
    def resolve_executable_path(executable: str) -> str:
        """Resolve executable path, checking absolute path, PATH, and Windows App Paths registry.

        Args:
            executable: File name or path of the executable.

        Returns:
            Resolved executable path or the original string.
        """
        expanded = os.path.expandvars(executable).strip('"')
        path_obj = Path(expanded)
        if path_obj.is_absolute() and path_obj.exists():
            return str(path_obj)

        which_path = shutil.which(expanded)
        if which_path:
            return which_path

        if sys.platform == "win32":
            try:
                import winreg

                target_names = [expanded]
                if not expanded.lower().endswith(".exe"):
                    target_names.append(f"{expanded}.exe")

                for name in target_names:
                    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                        try:
                            with winreg.OpenKey(
                                root, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{name}"
                            ) as key:
                                val, _ = winreg.QueryValueEx(key, "")
                                if val:
                                    val_expanded = os.path.expandvars(str(val).strip('"'))
                                    if Path(val_expanded).exists():
                                        return val_expanded
                        except OSError:
                            pass
            except ImportError:
                pass

        return expanded

    @staticmethod
    def run_command(
        args: Sequence[str],
        cwd: str | Path | None = None,
        timeout: float = 30.0,
        capture_output: bool = True,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Execute a process safely using an argument list with shell=False strictly enforced.

        Args:
            args: Command arguments as a sequence of strings (e.g. ['python', 'script.py']).
            cwd: Working directory for the process.
            timeout: Maximum execution time in seconds.
            capture_output: Whether to capture stdout and stderr.
            check: If True, raises CalledProcessError on non-zero exit code.

        Returns:
            subprocess.CompletedProcess instance.

        Raises:
            ProcessSecurityError: If args is a raw string or shell=True attempt detected.
        """
        if isinstance(args, (str, bytes)):
            raise ProcessSecurityError(
                "Execution rejected: Commands must be provided as a sequence of arguments, not a string."
            )

        if not args or not str(args[0]).strip():
            raise ProcessSecurityError("Execution rejected: Command argument list cannot be empty.")

        cmd_list = [str(arg) for arg in args]

        # Explicitly enforce shell=False; arguments strictly validated as sequence
        return subprocess.run(  # nosec: B603
            cmd_list,
            shell=False,
            cwd=str(cwd) if cwd else None,
            timeout=timeout,
            capture_output=capture_output,
            text=True,
            check=check,
        )

    @staticmethod
    def launch_allowlisted_app(
        app_name: str,
        allowlist: dict[str, str],
        extra_args: Sequence[str] | None = None,
    ) -> subprocess.Popen[str]:
        """Launch an application strictly from an approved allowlist.

        Args:
            app_name: Alias or name in the allowlist (e.g. 'notepad').
            allowlist: Mapping of allowed app names to executable paths.
            extra_args: Optional validated argument list.

        Returns:
            subprocess.Popen instance of the launched process.

        Raises:
            ProcessSecurityError: If app_name is not in the allowlist or launch fails.
        """
        normalized_name = app_name.strip().lower()
        if normalized_name not in allowlist:
            raise ProcessSecurityError(
                f"Unauthorized app launch rejected: '{app_name}' is not in config.yaml allowlist."
            )

        executable = allowlist[normalized_name]
        resolved_exe = SafeProcessRunner.resolve_executable_path(executable)
        cmd = [resolved_exe]
        if extra_args:
            if isinstance(extra_args, (str, bytes)):
                raise ProcessSecurityError("Extra arguments must be a list of strings, not a string.")
            cmd.extend([str(a) for a in extra_args])

        try:
            # shell=False is strictly enforced on allowlisted binaries
            return subprocess.Popen(cmd, shell=False, text=True)  # nosec: B603
        except (FileNotFoundError, OSError) as e:
            raise ProcessSecurityError(
                f"Application executable could not be launched for '{app_name}' ({resolved_exe}): {e}"
            ) from e
