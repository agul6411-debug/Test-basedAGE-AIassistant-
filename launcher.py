"""AGE Assistant - Desktop Application Launcher.

Unified entry point for the standalone desktop application.
Handles:
  1. Booting the local AGEServer engine.
  2. Polling loopback 127.0.0.1:8765 until the server & auth token are ready.
  3. Launching Google Chrome or Microsoft Edge in standalone App Window mode (--app).
  4. Clean lifecycle management (shutting down server when the UI window closes).
  5. Command-line dispatching for subprocesses (e.g. --hand-mouse).
"""

import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


def get_base_dir() -> Path:
    """Return the application root directory."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()
    cwd = Path.cwd().resolve()
    if (cwd / "config.yaml").exists():
        return cwd
    return Path(__file__).resolve().parent


def find_app_browser() -> str | None:
    """Find installed Chrome or Edge executable for chromeless standalone app window."""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


def wait_for_server(port: int = 8765, timeout: float = 20.0) -> str | None:
    """Poll the local token endpoint until the server is ready. Returns auth token."""
    start_time = time.monotonic()
    token_url = f"http://127.0.0.1:{port}/api/token"

    while time.monotonic() - start_time < timeout:
        try:
            req = urllib.request.Request(token_url, headers={"User-Agent": "AGE-Launcher"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    token = data.get("token")
                    if token:
                        return token
        except (urllib.error.URLError, ConnectionResetError, OSError):
            pass
        time.sleep(0.3)

    return None


def run_server_thread() -> None:
    """Run AGEServer inside an asyncio event loop in a dedicated thread."""
    import asyncio
    from core.server.runner import main as server_main
    server_main()


def main() -> None:
    """Main launcher entrypoint."""
    # Ensure current working directory is application root
    base_dir = get_base_dir()
    os.chdir(base_dir)

    # Subprocess dispatch: Hand mouse
    if "--hand-mouse" in sys.argv:
        from hand_mouse.runner import main as hm_main
        hm_main()
        return

    # Subprocess dispatch: Server only
    if "--server" in sys.argv:
        from core.server.runner import main as srv_main
        srv_main()
        return

    print("=" * 55)
    print("      AGE - MY BEST FRIEND AI (Desktop Application)")
    print("=" * 55)
    print(f"[*] Base directory: {base_dir}")

    # Check if server is already running on port 8765
    token = wait_for_server(port=8765, timeout=1.5)
    server_thread = None

    if token:
        print("[OK] AGEServer is already running on port 8765.")
    else:
        print("[*] Starting AGEServer engine...")
        server_thread = threading.Thread(target=run_server_thread, daemon=True)
        server_thread.start()

        # Wait for server to become responsive
        print("[*] Waiting for engine initialization...")
        token = wait_for_server(port=8765, timeout=25.0)
        if not token:
            print("[ERROR] Server failed to start within 25 seconds.")
            sys.exit(1)
        print("[OK] Engine initialized successfully.")

    # Determine launch URL with token
    app_url = f"http://127.0.0.1:8765/?token={token}"
    print(f"[*] Connecting client: {app_url}")

    # Find standalone browser
    browser_exe = find_app_browser()
    browser_proc = None

    if browser_exe:
        browser_name = "Chrome" if "chrome" in browser_exe.lower() else "Edge"
        print(f"[*] Launching {browser_name} in standalone App Window mode...")
        cmd = [
            browser_exe,
            f"--app={app_url}",
            "--window-size=1120,780",
            "--disable-extensions",
        ]
        try:
            browser_proc = subprocess.Popen(cmd)
        except Exception as e:
            print(f"[WARN] Failed to launch {browser_name}: {e}. Falling back to default browser.")
            webbrowser.open(app_url)
    else:
        print("[*] Opening default system browser...")
        webbrowser.open(app_url)

    print("\n" + "=" * 55)
    print(" [READY] AGE Assistant is running!")
    print(" - Press Ctrl+Space anytime for Voice Assistant")
    print(" - Close the application window to exit")
    print("=" * 55 + "\n")

    # Monitor browser window process if launched directly
    if browser_proc:
        try:
            browser_proc.wait()
            print("[*] Application window closed by user. Exiting cleanly...")
        except KeyboardInterrupt:
            print("\n[*] Interrupted by user.")
        finally:
            try:
                browser_proc.terminate()
            except Exception:
                pass
    else:
        # Keep process alive if opened via webbrowser.open()
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("\n[*] Exiting...")

    sys.exit(0)


if __name__ == "__main__":
    main()
