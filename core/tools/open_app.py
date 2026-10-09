"""Tool to open applications, standard folders, media files, videos, photos, and documents.

Allows opening any installed Windows application (via Start Menu, App Paths registry, PATH, or URIs)
and any user file, photo, video, or document using native Windows associations.
"""

import glob
import os
import re
import shutil
import subprocess  # nosec: B404
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from core.config import load_config
from core.logger import get_logger
from core.safety.process_runner import ProcessSecurityError, SafeProcessRunner
from core.tools.base import BaseTool, ToolResult
from core.tools.registry import registry

logger = get_logger("tools.open_app")

ALLOWED_APPLICATIONS = {
    "notepad",
    "calc",
    "chrome",
    "edge",
    "explorer",
    "vscode",
    "word",
    "excel",
    "powerpoint",
    "onenote",
    "outlook",
    "access",
    "paint",
    "taskmanager",
    "controlpanel",
    "snippingtool",
    "media",
    "downloads",
    "documents",
    "desktop",
    "pictures",
    "videos",
    "music",
}

APP_ALIASES: dict[str, str] = {
    "calculator": "calc",
    "vs code": "vscode",
    "visual studio code": "vscode",
    "code": "vscode",
    "google chrome": "chrome",
    "google": "chrome",
    "browser": "chrome",
    "microsoft edge": "edge",
    "file explorer": "explorer",
    "files": "explorer",
    "my computer": "explorer",
    "this pc": "explorer",
    "word": "word",
    "ms word": "word",
    "microsoft word": "word",
    "excel": "excel",
    "ms excel": "excel",
    "microsoft excel": "excel",
    "powerpoint": "powerpoint",
    "ppt": "powerpoint",
    "ms powerpoint": "powerpoint",
    "slides": "powerpoint",
    "paint": "paint",
    "ms paint": "paint",
    "onenote": "onenote",
    "outlook": "outlook",
    "mail": "outlook",
    "email": "outlook",
    "access": "access",
    "ms access": "access",
    "task manager": "taskmanager",
    "tasks": "taskmanager",
    "control panel": "controlpanel",
    "settings": "settings",
    "camera": "camera",
    "snipping tool": "snippingtool",
    "snip": "snippingtool",
    "screenshot": "snippingtool",
    "media player": "media",
    "music": "media",
    "player": "media",
}

STANDARD_FOLDERS: dict[str, Path] = {
    "downloads": Path.home() / "Downloads",
    "download": Path.home() / "Downloads",
    "downloads folder": Path.home() / "Downloads",
    "documents": Path.home() / "Documents",
    "my documents": Path.home() / "Documents",
    "documents folder": Path.home() / "Documents",
    "desktop": Path.home() / "Desktop",
    "desktop folder": Path.home() / "Desktop",
    "pictures": Path.home() / "Pictures",
    "pictures folder": Path.home() / "Pictures",
    "photos": Path.home() / "Pictures",
    "photos folder": Path.home() / "Pictures",
    "gallery": Path.home() / "Pictures",
    "music": Path.home() / "Music",
    "music folder": Path.home() / "Music",
    "songs": Path.home() / "Music",
    "videos": Path.home() / "Videos",
    "videos folder": Path.home() / "Videos",
    "video folder": Path.home() / "Videos",
    "c drive": Path("C:/"),
    "c": Path("C:/"),
    "d drive": Path("D:/"),
    "d": Path("D:/"),
}

KNOWN_WINDOWS_PROTOCOLS: dict[str, str] = {
    "camera": "microsoft.windows.camera:",
    "settings": "ms-settings:",
    "photos": "ms-photos:",
    "store": "ms-windows-store:",
    "calc": "calc.exe",
    "calculator": "calc.exe",
    "notepad": "notepad.exe",
    "paint": "mspaint.exe",
    "taskmanager": "taskmgr.exe",
    "controlpanel": "control.exe",
    "snippingtool": "snippingtool.exe",
    "explorer": "explorer.exe",
}

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".flv", ".3gp", ".m4v"}
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".ico", ".svg"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".aac", ".flac", ".m4a", ".wma", ".ogg"}
DOC_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".txt", ".csv", ".md", ".json", ".xml", ".py", ".html"}


def _launch_target(target: str | Path) -> bool:
    """Launch target using Windows native ShellExecute (os.startfile) or safe subprocess fallback."""
    target_str = str(target)
    if hasattr(os, "startfile"):
        try:
            os.startfile(target_str)  # type: ignore[attr-defined]
            return True
        except Exception as e:  # noqa: BLE001
            logger.warning("os.startfile failed for %s: %s", target_str, e)

    # Safe subprocess fallback for executables or non-Windows environments
    try:
        subprocess.Popen([target_str], shell=False)  # nosec: B603
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("subprocess.Popen failed for %s: %s", target_str, e)
        return False


def find_installed_app(app_name: str) -> str | Path | None:
    """Locate any installed Windows application via shortcuts, registry, PATH, or URIs."""
    clean_q = app_name.strip().lower()

    # 1. Direct protocol check
    if clean_q in KNOWN_WINDOWS_PROTOCOLS:
        return KNOWN_WINDOWS_PROTOCOLS[clean_q]

    # 2. Check allowlist from config if defined
    try:
        config = load_config()
        if clean_q in config.safety.app_allowlist:
            exe = config.safety.app_allowlist[clean_q]
            resolved = SafeProcessRunner.resolve_executable_path(exe)
            if Path(resolved).exists():
                return resolved
    except Exception:  # noqa: BLE001
        pass

    # 3. Check Start Menu shortcuts (.lnk files across all users)
    norm_q = re.sub(r"[^a-z0-9]", "", clean_q)
    start_dirs = [
        Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"),
        Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    for sdir in start_dirs:
        if not sdir.exists():
            continue
        try:
            for lnk in sdir.rglob("*.lnk"):
                stem_lower = lnk.stem.lower()
                norm_stem = re.sub(r"[^a-z0-9]", "", stem_lower)
                if norm_q and (norm_q == norm_stem or norm_q in norm_stem):
                    return lnk
                if clean_q in stem_lower:
                    return lnk
        except OSError:
            continue

    # 4. Check Windows Registry App Paths (HKLM & HKCU)
    if sys.platform == "win32":
        try:
            import winreg

            target_exes = [f"{clean_q}.exe", clean_q]
            for t_exe in target_exes:
                for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                    try:
                        with winreg.OpenKey(
                            root, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{t_exe}"
                        ) as key:
                            val, _ = winreg.QueryValueEx(key, "")
                            if val:
                                p = Path(os.path.expandvars(str(val).strip('"')))
                                if p.exists():
                                    return p
                    except OSError:
                        pass
        except ImportError:
            pass

    # 5. Check System PATH via shutil.which
    which_res = shutil.which(clean_q) or shutil.which(f"{clean_q}.exe")
    if which_res:
        return which_res

    # 6. Check common Program Files directories
    prog_dirs = [
        Path(r"C:\Program Files"),
        Path(r"C:\Program Files (x86)"),
        Path.home() / "AppData" / "Local" / "Programs",
    ]
    for pdir in prog_dirs:
        if not pdir.exists():
            continue
        try:
            for exe in pdir.rglob("*.exe"):
                stem_lower = exe.stem.lower()
                norm_stem = re.sub(r"[^a-z0-9]", "", stem_lower)
                if norm_q and norm_q == norm_stem:
                    return exe
        except OSError:
            continue

    return None


def find_user_media_or_file(query: str, category: str | None = None) -> Path | None:
    """Find any file, photo, video, or document across user home directories."""
    clean_q = query.strip().lower()
    if not clean_q:
        return None

    # Direct existing path
    direct_p = Path(query)
    if direct_p.exists():
        return direct_p

    home = Path.home()
    if category == "video":
        search_dirs = [home / "Videos", home / "Downloads", home / "Desktop"]
    elif category in ("photo", "picture", "image"):
        search_dirs = [home / "Pictures", home / "Downloads", home / "Desktop"]
    elif category in ("audio", "music", "song"):
        search_dirs = [home / "Music", home / "Downloads", home / "Desktop"]
    else:
        search_dirs = [
            home / "Desktop",
            home / "Documents",
            home / "Downloads",
            home / "Pictures",
            home / "Videos",
            home / "Music",
        ]

    norm_q = re.sub(r"[^a-z0-9]", "", clean_q)
    q_words = [w for w in re.split(r"[^a-z0-9]+", clean_q) if w]

    # Pass 1 & 2: Match files inside search directories up to 3 levels deep
    for sdir in search_dirs:
        if not sdir.exists():
            continue
        try:
            for root, _, files in os.walk(str(sdir)):
                for fname in files:
                    fpath = Path(root) / fname
                    stem_lower = fpath.stem.lower()
                    ext = fpath.suffix.lower()

                    if category == "video" and ext not in VIDEO_EXTENSIONS:
                        continue
                    if category in ("photo", "picture", "image") and ext not in PHOTO_EXTENSIONS:
                        continue
                    if category in ("audio", "music", "song") and ext not in AUDIO_EXTENSIONS:
                        continue

                    # Exact name or stem match
                    if clean_q == fname.lower() or clean_q == stem_lower:
                        return fpath

                    # Normalized alphanumeric match (handles parentheses, spaces, punctuation)
                    norm_stem = re.sub(r"[^a-z0-9]", "", stem_lower)
                    if norm_q and norm_q in norm_stem:
                        return fpath

                    # Token subset match
                    if q_words and all(w in stem_lower for w in q_words):
                        return fpath
        except OSError:
            continue

    return None


def find_any_media() -> Path | None:
    """Find any playable video or song on the user's computer."""
    home = Path.home()
    for sdir in [home / "Videos", home / "Music", home / "Downloads", home / "Desktop"]:
        if not sdir.exists():
            continue
        try:
            for root, _, files in os.walk(str(sdir)):
                for f in files:
                    p = Path(root) / f
                    if p.suffix.lower() in (VIDEO_EXTENSIONS | AUDIO_EXTENSIONS):
                        return p
        except OSError:
            continue
    return None


class OpenAppSchema(BaseModel):
    """Schema for opening an application, standard folder, video, photo, or document."""
    app_name: str = Field(description="Name or alias of application, standard folder, video, photo, or document")


class OpenAppTool(BaseTool):
    """Launches any application, opens folders, or plays videos, photos, and files."""

    name = "open_app"
    description = "Open any desktop application, standard folder, video, photo, or document."
    is_dangerous = False
    args_schema = OpenAppSchema

    def execute(self, app_name: str, **kwargs: Any) -> ToolResult:
        clean_raw = app_name.strip()
        clean_lower = clean_raw.lower()

        # Handle 'play any media' request
        if clean_lower in ("play_any_media", "any video", "any song", "any media", "random video", "random song"):
            any_file = find_any_media()
            if any_file:
                success = _launch_target(any_file)
                return ToolResult(
                    success=success,
                    message=f"Aapke computer par '{any_file.name}' play kar raha hoon." if success else f"Failed to play '{any_file.name}'.",
                    data={"file": str(any_file), "path": str(any_file)},
                )
            return ToolResult(
                success=False,
                message="Computer par koi song ya video nahi mili.",
            )

        # 0. Check category prefixes (e.g. 'video funny', 'photo screenshot 158', 'file report')
        category: str | None = None
        search_query = clean_lower

        for cat_prefix in ("video ", "videos "):
            if clean_lower.startswith(cat_prefix):
                category = "video"
                search_query = clean_lower[len(cat_prefix):].strip()
                break

        for cat_prefix in ("photo ", "photos ", "picture ", "pictures ", "image ", "images "):
            if clean_lower.startswith(cat_prefix):
                category = "photo"
                search_query = clean_lower[len(cat_prefix):].strip()
                break

        for cat_prefix in ("file ", "document ", "doc ", "pdf "):
            if clean_lower.startswith(cat_prefix):
                category = "document"
                search_query = clean_lower[len(cat_prefix):].strip()
                break

        # 1. Check standard user folders directly (Downloads, Documents, Pictures, Videos, Desktop, etc.)
        target_folder_name = search_query if not search_query else clean_lower
        if target_folder_name in STANDARD_FOLDERS:
            folder_path = STANDARD_FOLDERS[target_folder_name]
            if folder_path.exists():
                success = _launch_target(folder_path)
                return ToolResult(
                    success=success,
                    message=f"Opened {target_folder_name} folder." if success else f"Failed to open {target_folder_name}.",
                    data={"folder": str(folder_path)},
                )

        # 2. If a specific media category was requested or file query provided, search user files
        if category or any(clean_lower.endswith(ext) for ext in VIDEO_EXTENSIONS | PHOTO_EXTENSIONS | DOC_EXTENSIONS | AUDIO_EXTENSIONS):
            found_media = find_user_media_or_file(search_query or clean_lower, category=category)
            if found_media:
                success = _launch_target(found_media)
                return ToolResult(
                    success=success,
                    message=f"Opened '{found_media.name}'." if success else f"Failed to open '{found_media.name}'.",
                    data={"file": str(found_media), "path": str(found_media)},
                )

        # 3. Check installed applications and aliases
        resolved_name = APP_ALIASES.get(clean_lower, clean_lower)
        app_target = find_installed_app(resolved_name)
        if app_target:
            success = _launch_target(app_target)
            return ToolResult(
                success=success,
                message=f"Opened {resolved_name}." if success else f"Failed to open {resolved_name}.",
                data={"app": str(app_target)},
            )

        # 4. Check general user files (Desktop, Documents, Downloads, Pictures, Videos, Music)
        found_file = find_user_media_or_file(clean_lower)
        if found_file:
            success = _launch_target(found_file)
            return ToolResult(
                success=success,
                message=f"Opened file '{found_file.name}'." if success else f"Failed to open '{found_file.name}'.",
                data={"file": str(found_file), "path": str(found_file)},
            )

        # 5. Direct path fallback
        direct_path = Path(clean_raw)
        if direct_path.exists():
            success = _launch_target(direct_path)
            return ToolResult(
                success=success,
                message=f"Opened '{direct_path.name}'." if success else f"Failed to open '{direct_path.name}'.",
                data={"path": str(direct_path)},
            )

        return ToolResult(
            success=False,
            message=f"Application, file, photo, ya video '{app_name}' nahi mili (not permitted or not found).",
        )


registry.register(OpenAppTool())
