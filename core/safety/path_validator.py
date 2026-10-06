"""Path sanitization and path-traversal prevention.

Security Rule 13:
Validate and sanitize all file paths (no path traversal).
Layout data and logs live only inside data/.
"""

import re
from pathlib import Path

from core.safety.base import SecurityException

# Characters prohibited in Windows filenames
INVALID_WIN_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class PathTraversalError(SecurityException):
    """Raised when a path attempts to escape its designated root directory."""


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename by removing path separators and invalid Windows characters.

    Args:
        filename: Proposed file name without directory components.

    Returns:
        Safe filename string.

    Raises:
        PathTraversalError: If filename contains directory traversal elements.
    """
    if not filename or not filename.strip():
        raise PathTraversalError("Filename cannot be empty or whitespace.")

    # Guard against null bytes
    if "\x00" in filename:
        raise PathTraversalError("Null bytes are prohibited in filenames.")

    # Strip whitespace
    clean_name = filename.strip()

    # Reject any directory navigation components
    if "/" in clean_name or "\\" in clean_name or ".." in clean_name:
        raise PathTraversalError(f"Directory navigation forbidden in filename: '{filename}'")

    # Replace invalid Windows filename characters with underscores
    sanitized = INVALID_WIN_CHARS.sub("_", clean_name)

    if sanitized in (".", ".."):
        raise PathTraversalError(f"Reserved filename '{sanitized}' is not permitted.")

    return sanitized


def validate_path_within_root(target_path: str | Path, root_dir: str | Path) -> Path:
    """Validate that target_path strictly resolves within root_dir.

    Args:
        target_path: Relative or absolute path to validate.
        root_dir: The directory confining the target path.

    Returns:
        Resolved safe Path object.

    Raises:
        PathTraversalError: If target_path escapes root_dir.
    """
    resolved_root = Path(root_dir).resolve()
    resolved_target = (resolved_root / target_path).resolve() if not Path(target_path).is_absolute() else Path(target_path).resolve()

    try:
        # Python 3.9+ is_relative_to
        if not resolved_target.is_relative_to(resolved_root):
            raise PathTraversalError(
                f"Access denied: Path '{target_path}' escapes confinement root '{root_dir}'"
            )
    except AttributeError:
        # Fallback for older python compatibility if needed
        try:
            resolved_target.relative_to(resolved_root)
        except ValueError:
            raise PathTraversalError(
                f"Access denied: Path '{target_path}' escapes confinement root '{root_dir}'"
            )

    return resolved_target


def get_data_path(relative_path: str | Path, project_root: str | Path | None = None) -> Path:
    """Ensure a given relative path resolves strictly within the project's data/ directory.

    Args:
        relative_path: Path relative to data/.
        project_root: Optional root directory of the project. Defaults to current working dir.

    Returns:
        Safe resolved Path object strictly inside data/.
    """
    root = Path(project_root).resolve() if project_root else Path.cwd().resolve()
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return validate_path_within_root(relative_path, data_dir)
