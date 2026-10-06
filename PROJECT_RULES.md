You are the lead engineer for a personal, offline desktop voice assistant
named "AGE", inside an app called "MY BEST FRIEND AI". Save this entire
message as PROJECT_RULES.md in the project root. Re-read it at the start of
every task and follow it strictly.

## Product
- Windows 10/11 laptop, 16 GB RAM, NO GPU. Single user (personal use).
- English-only voice commands. Fully offline after first model download.
- Features: (1) voice control, (2) hand-gesture mouse via webcam,
  (3) desktop layout save/restore across shutdown.
- NO WhatsApp or social-media features.

## Architecture
- Python 3.11 core (the brain) + separate Python process for hand mouse
  + Flutter Desktop (Windows) UI. UI and core talk over a local WebSocket.
- Voice: sounddevice, Porcupine wake word "Hey AGE" (hotkey Ctrl+Space as
  backup), Silero VAD, faster-whisper base.en, Piper TTS (English voice).
- Brain: Layer 1 = rule/keyword router. Layer 2 = Ollama + Qwen2.5 3B with
  tool calling, only when no rule matches.
- Hand mouse: OpenCV + MediaPipe Hands + One Euro filter + pynput.
- Windows control: pywin32, pywinauto, pycaw. Storage: SQLite + YAML config.
- Folder layout: core/ (voice, brain, tools, layout, safety, server),
  hand_mouse/, ui/, data/, models/, tests/.

## SECURITY RULES (non-negotiable)
1. WebSocket binds to 127.0.0.1 ONLY, never 0.0.0.0. Require a random
   per-session auth token (stored in a user-only file) and check Origin.
2. Never use shell=True, eval, exec, or os.system. Use subprocess with an
   argument list.
3. LLM output is UNTRUSTED. Tool calls from the LLM must be validated
   against an allowlist and a strict schema (pydantic) before running.
   Transcribed speech is also untrusted input.
4. Apps can only be launched from an allowlist in config.yaml, never from
   arbitrary strings.
5. Destructive actions (delete, shutdown, restart, close-all, overwrite)
   ALWAYS need a spoken or button confirmation. No bypass flag.
6. Secrets (e.g. Porcupine access key) live in .env only. .env is in
   .gitignore. Never hardcode or log secrets.
7. Never store raw audio or camera frames on disk. Never send any data over
   the internet at runtime. No telemetry. Only models are downloaded, once,
   from official sources, with checksum verification.
8. Pin every dependency to an exact version (requirements.lock with hashes,
   pubspec.lock committed). Prefer well-known packages.
9. Run everything as a normal user. Never request admin rights.
10. Add an emergency-stop hotkey (Ctrl+Shift+Esc) that stops mic, camera,
    hand mouse, and any running action immediately.
11. Mic and camera must have a visible on/off indicator in the UI.
12. Log actions (what, when, result) but never log full transcripts of
    sensitive text typed by the user.
13. Validate and sanitize all file paths (no path traversal). Layout data
    and logs live only inside data/.

## Process rules (also non-negotiable)
- Work phase by phase. Do ONLY the phase I ask for. Show a short plan
  first and wait for my "go".
- After each phase, stop and show a git diff summary. Commit ONLY after I
  say "commit". One clear commit message per phase.
- Before installing ANY package, list its exact name, version, publisher,
  and purpose, and wait for my approval. Warn me about look-alike or
  typosquatted names.
- Never ask me to paste secrets into chat. Tell me to put them in .env
  myself. Never print secret values in logs or output.
- If a security rule can't be followed, STOP and tell me. Never say
  "we'll fix it later" and never leave TODOs for security issues.
- Keep each phase self-contained so I can continue it in a fresh chat
  using only PROJECT_RULES.md and the repo.
- For hardware parts (mic, camera, mouse), write pytest tests for logic and
  give me numbered manual test steps, then wait for my result.
- Small, readable modules with type hints and docstrings. No giant files.
- At the end of each phase: list what was built, how to run it, known
  limits, and run bandit + pip-audit and report findings.
- If something is impossible or fragile on Windows, say so honestly and
  propose an alternative. Never fake it.
