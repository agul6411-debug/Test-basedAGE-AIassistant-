# AGE (MY BEST FRIEND AI)

> **Personal, 100% Offline Desktop Voice Assistant for Windows 10/11**  
> Built with Python 3.11, Flutter Desktop, Ollama LLM, MediaPipe Hands, and Faster-Whisper.

---

## Overview

**AGE** is a privacy-first, fully offline personal desktop voice assistant developed inside **MY BEST FRIEND AI**. It runs entirely on local consumer hardware (Windows 10/11, 16 GB RAM, no GPU required) with **zero internet connectivity required after initial setup**, **zero telemetry**, and **zero external cloud API calls**.

### Key Capabilities
1. **Offline Voice Pipeline**:
   - Ultra-low-latency wake word detection ("Hey AGE") via Picovoice Porcupine (with `Ctrl+Space` push-to-talk backup).
   - Voice Activity Detection (VAD) via Silero ONNX.
   - Speech-to-Text (STT) via `faster-whisper base.en` running locally on CPU with CTranslate2.
   - Text-to-Speech (TTS) via `piper-tts` with high-fidelity natural English voice (`en_US-lessac-medium`).
2. **Two-Layer Intelligent Router**:
   - **Layer 1**: Instant deterministic rule-based keyword router (< 5 ms latency) handling volume, brightness, app launching, window management, desktop layouts, and search.
   - **Layer 2**: Local LLM fallback via Ollama (`qwen2.5:3b`) with strict Pydantic tool calling schema validation and guardrails.
3. **In-Memory Hand-Gesture Mouse**:
   - Separate isolated subprocess using OpenCV and MediaPipe Hands at 640x480 (~30 FPS).
   - Central webcam viewport mapped to screen with One Euro filter jitter smoothing.
   - Index fingertip pointer movement, pinch-to-click, two-finger scroll, hold-to-drag.
   - Camera frames processed strictly in RAM; **never saved to disk or transmitted**.
4. **Desktop Layout Manager**:
   - Captures and restores desktop icon coordinates and open window states to SQLite across reboots.
   - Auto-saves every 5 minutes and on clean shutdown (maintains 10 snapshots).
   - Normal user logon autostart via Windows Task Scheduler (`/RL LIMITED`, zero admin rights).
5. **Flutter Windows Desktop UI**:
   - Dark theme styling with Amber (`#FFB547`) mic and Mint (`#5EEAD4`) success accents.
   - Real-time pipeline state visualization (**Idle**, **Listening**, **Thinking**, **Speaking**).
   - Dedicated Controls, Conversation Audit Log, and Settings screens.
   - Always-visible **Emergency Stop** (`Ctrl+Shift+Esc`) and interactive confirmation modals for destructive operations.

---

## System Requirements

- **Operating System**: Windows 10 or Windows 11 (64-bit).
- **RAM**: 16 GB system memory (no GPU required).
- **Python**: Python 3.11.x x64 ([python.org](https://www.python.org/downloads/)).
- **Flutter**: Flutter SDK 3.x+ (optional if using pre-built binary, required for compiling UI).
- **Ollama**: Local Ollama runtime ([ollama.com](https://ollama.com/)) with `qwen2.5:3b` model.
- **Hardware**: Standard laptop webcam and microphone.

---

## Quick Start (Installation & Setup)

### 1. Clone & Set Up Ollama
```powershell
git clone <repo-url> "C:\MY BEST FRIEND AI"
cd "C:\MY BEST FRIEND AI"

# Install Ollama and pull local model
ollama pull qwen2.5:3b
```

### 2. Run Automated Setup (`setup.ps1`)
Run the installer script to create the `.venv`, install hash-locked dependencies, download models with checksum verification, and prepare the Flutter UI:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

*Optional Switches*:
- `-EnableAutostart`: Registers Windows Task Scheduler task to start AGE on logon as normal user.
- `-SkipModels`: Skips model downloads if already present.

### 3. Configure Secrets (Optional)
If using Porcupine wake word detection, add your free personal key to `.env`:
```ini
PICOVOICE_ACCESS_KEY=your_key_here
```
*(If no key is provided, the assistant seamlessly uses the `Ctrl+Space` push-to-talk hotkey).*

### 4. One-Click Launch (`run.ps1`)
Start both the Core WebSocket Server and the Flutter Desktop UI:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

*(For headless/terminal-only mode, run `.\run.ps1 -Headless`)*.

---

## Complete Voice Commands Reference

| Category | Command Examples | Router Layer | Requires Confirmation? | Action Executed |
| :--- | :--- | :---: | :---: | :--- |
| **System Audio** | `"volume up"`, `"turn down volume"`, `"set volume to 40"`, `"mute audio"` | Layer 1 | No | Adjusts Windows master audio via Core Audio (pycaw). |
| **Display** | `"brightness up"`, `"lower brightness"`, `"set brightness to 70"` | Layer 1 | No | Adjusts laptop screen brightness via WMI/VCP. |
| **App Launch** | `"open notepad"`, `"launch calc"`, `"open paint"`, `"open file explorer"` | Layer 1 | No | Launches allowlisted apps from `config.yaml` using list arguments. |
| **Window State** | `"minimize window"`, `"maximize window"`, `"close notepad"` | Layer 1 | No | Manipulates active or named window via Win32 API. |
| **Lock Screen** | `"lock the screen"`, `"lock workstation"` | Layer 1 | **YES** | Invokes `LockWorkStation` after verbal/dialog confirmation. |
| **Shutdown** | `"shut down laptop"`, `"power off system"` | Layer 1 | **YES** | Invokes `shutdown /s /t 0` after explicit confirmation. |
| **Desktop Layout**| `"save my desktop"`, `"save layout snapshot"` | Layer 1 | No | Saves icon positions and window states to `data/layout.db`. |
| **Restore Layout**| `"restore my desktop"`, `"restore desktop layout"` | Layer 1 | **YES** | Restores open allowlisted windows and icon positions. |
| **Hand Mouse** | `"start hand mouse"`, `"stop hand mouse"` | Layer 1 | No | Launches or terminates the `hand_mouse/` subprocess. |
| **Media & Web** | `"search youtube for lofi jazz"`, `"search python docs"` | Layer 1 | No | Opens browser directly to query URL (no background web scraping). |
| **Typing** | `"type hello world"`, `"type my notes"` | Layer 1 | No | Injects keystrokes into current focus (sanitized in audit logs). |
| **General Q&A** | `"what is the capital of France?"`, `"summarize quantum computing"` | Layer 2 | No | Dispatched to local Ollama (`qwen2.5:3b`) without internet. |
| **Emergency** | `Ctrl+Shift+Esc` or UI **STOP** button | Direct | **Immediate** | Hard kill of microphone, webcam, mouse, and any running tool. |

---

## Developer Guide: Adding a New Tool

All tools in AGE inherit from the abstract [`Tool`](file:///c:/MY%20BEST%20FRIEND%20AI/core/tools/base.py) base class and require a Pydantic argument schema.

### Step 1: Define Your Tool Class
Create a new file in `core/tools/my_tool.py`:

```python
from pydantic import BaseModel, Field
from core.tools.base import Tool

class MyToolInput(BaseModel):
    query: str = Field(..., description="Target query string", max_length=100)

class MyCustomTool(Tool):
    name: str = "my_custom_tool"
    description: str = "Performs a safe, validated action on Windows."
    args_schema = MyToolInput
    is_dangerous: bool = False  # Set to True if it modifies files, shuts down, or deletes data

    def execute(self, query: str) -> str:
        # Security Rule 2: Never use shell=True, eval, or os.system
        # Security Rule 13: Sanitize all paths with validate_path_within_root
        return f"Processed query: {query}"
```

### Step 2: Register the Tool
In `core/tools/__init__.py`:
```python
from core.tools.registry import registry
from core.tools.my_tool import MyCustomTool

registry.register(MyCustomTool())
```

### Step 3: Add Unit Tests
In `tests/test_tools.py`, write a test verifying schema validation, execution, and confirmation requirements:
```python
def test_my_custom_tool():
    tool = registry.get_tool("my_custom_tool")
    assert tool is not None
    res = tool.execute(query="test")
    assert "Processed query: test" in res
```

Run test suite:
```powershell
powershell -ExecutionPolicy Bypass -File .\check.ps1
```

---

## Backup & Recovery

All persistent application data lives strictly inside the `data/` directory (Rule 13):

| File / Folder | Contents | Backup Strategy |
| :--- | :--- | :--- |
| `data/layout.db` | SQLite database storing window and icon layout snapshots | Copy file while AGE is closed. |
| `data/logs/actions.log` | Structured JSON audit trail of all executed commands | Copy or archive log files periodically. |
| `data/logs/age.log` | Rotating system diagnostic logs (max 5 MB, 5 backups) | Retained automatically. |
| `data/sessions/session.token` | Temporary per-session 256-bit authentication token | Ephemeral; recreated automatically on start. |

### How to Back Up
```powershell
# Create a timestamped backup of the data folder
$backupZip = "AGE_Data_Backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').zip"
Compress-Archive -Path "data" -DestinationPath $backupZip
Write-Host "Backup created: $backupZip"
```

### How to Restore
```powershell
Expand-Archive -Path "AGE_Data_Backup_xxxx.zip" -DestinationPath "C:\MY BEST FRIEND AI" -Force
```

---

## Troubleshooting Guide

### 1. Microphone Not Detected or Voice Recognition Fails
- Verify your microphone is enabled in Windows Settings $\rightarrow$ Privacy & Security $\rightarrow$ Microphone.
- In `config.yaml`, check `voice.sample_rate` (default: 16000 Hz).
- Check that the Porcupine access key is valid in `.env`, or use the `Ctrl+Space` push-to-talk hotkey.

### 2. Hand Mouse Jitter or Camera Fails to Open
- Ensure your webcam is not in use by another application (Zoom, Teams, etc.).
- In `config.yaml`, change `hand_mouse.camera_index` if you have multiple cameras (0 is default laptop webcam, 1 is external USB).
- Hand mouse requires adequate lighting and hand position 0.5m–1.5m from the camera.
- Adjust `sensitivity` and `dead_zone` sliders on the UI **Controls** screen.

### 3. Desktop Icon Positions Not Restoring
- Right-click your desktop $\rightarrow$ View $\rightarrow$ ensure **"Auto arrange icons"** and **"Align icons to grid"** are **UNCHECKED**. When enabled, Windows Explorer overrides programmatic icon placement.
- Relaunching applications is restricted to the allowlist in `config.yaml`. Unlisted third-party windows are not launched.

### 4. Ollama Shows Offline in UI
- Confirm Ollama is running in the background: run `ollama list` in PowerShell.
- Verify `qwen2.5:3b` is installed: `ollama pull qwen2.5:3b`.
- Check that `http://127.0.0.1:11434` responds.

### 5. UI Connection Error (Code 4401)
- Verify `data/sessions/session.token` exists and is readable by your current user account.
- If corrupted, delete `data/sessions/session.token`; the Core runner will regenerate a fresh token on startup.

---

## Security & Verification Summary

AGE is built according to the 13 strict rules in `PROJECT_RULES.md`:
- **Static Analysis**: 0 issues found by Bandit (4,749 LOC scanned).
- **Dependency Audit**: 0 known vulnerabilities found across 84 locked dependencies by `pip-audit`.
- **Linter**: Clean pass by Ruff.
- **Flutter Analyzer**: 0 errors, 0 warnings.
- **Test Suite**: 123 automated Python unit/integration tests and Flutter widget tests passing cleanly.

For full details, review [`SECURITY_REPORT.md`](file:///c:/MY%20BEST%20FRIEND%20AI/SECURITY_REPORT.md).
