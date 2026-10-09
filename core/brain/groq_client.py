"""Groq Cloud API Client with Multi-Turn Conversation Memory.

Uses Groq's high-speed inference endpoint (https://api.groq.com/openai/v1/chat/completions)
with Llama-3.3 70B or Qwen 32B for near-instant (<500ms) human-like conversation,
deep general knowledge, and contextual memory with 0% CPU/GPU load on the user's laptop.
"""

import os
import re
from pathlib import Path
from typing import Any

import httpx

from core.logger import get_logger

logger = get_logger("brain.groq")

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"
def _get_project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()
    cwd = Path.cwd().resolve()
    if (cwd / "data").exists():
        return cwd
    return Path(__file__).resolve().parents[2]

PROJECT_ROOT = _get_project_root()
KEY_FILE_PATH = PROJECT_ROOT / "data" / "groq_key.txt"
FALLBACK_MODELS = [
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
]

GROQ_SYSTEM_PROMPT = (
    "You are AGE, a brilliant, warm, and witty AI companion and personal desktop assistant. "
    "You communicate fluently in friendly Roman Urdu (and English when spoken to in English). "
    "Rules: "
    "1. Speak like a caring, intelligent best friend (natural, human, and engaging). "
    "2. Keep responses concise and spoken-friendly (2 to 4 sentences max), unless the user explicitly asks for a detailed explanation or story. "
    "3. Use English/Latin alphabet ONLY (Roman Urdu e.g. 'Main bilkul theek hoon, aap sunayein'). "
    "   NEVER output Arabic or Perso-Arabic script (no اردو characters). "
    "4. Remember previous context from this conversation and answer follow-ups naturally. "
    "5. If the user asks about general knowledge, studies, recipes, coding, life advice, jokes, or stories, answer helpfully and enthusiastically. "
    "6. If the user asks to open an app, play a song/video, or search, append an action tag at the very end of your response: "
    "   - [ACTION: open_app <target>] (e.g. [ACTION: open_app chrome], [ACTION: open_app whatsapp], [ACTION: open_app play_any_media], [ACTION: open_app videos], [ACTION: open_app pictures]) "
    "   - [ACTION: youtube_search <query>] (e.g. [ACTION: youtube_search atif aslam]) "
    "   - [ACTION: set_volume <0-100>]"
)


class GroqClientError(Exception):
    """Base exception for Groq client errors."""


class GroqAuthError(GroqClientError):
    """Raised when Groq API key is missing or invalid."""


class GroqClient:
    """Super-fast cloud LLM client with multi-turn memory buffer."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_GROQ_MODEL,
        max_history_turns: int = 10,
        timeout_sec: float = 20.0,
    ) -> None:
        """Initialize Groq client.

        Args:
            api_key: Optional explicit Groq API key.
            model: Model ID to invoke on Groq (default: llama-3.3-70b-versatile).
            max_history_turns: Number of prior conversational exchanges to retain.
            timeout_sec: Maximum timeout for HTTP requests.
        """
        self._explicit_key = api_key
        self.model = model
        self.max_history_turns = max_history_turns
        self.timeout_sec = timeout_sec
        self._history: list[dict[str, str]] = []

    def get_api_key(self) -> str:
        """Resolve API key from explicit param, data/groq_key.txt, config, or env."""
        if self._explicit_key and self._explicit_key.strip():
            return self._explicit_key.strip()

        # 1. Check local key file (set via UI Settings)
        if KEY_FILE_PATH.exists():
            try:
                key_text = KEY_FILE_PATH.read_text(encoding="utf-8").strip()
                if key_text:
                    return key_text
            except Exception as e:
                logger.debug("Could not read %s: %s", KEY_FILE_PATH, e)

        # 2. Check config.yaml
        try:
            from core.config import load_config
            cfg = load_config()
            if getattr(cfg.brain, "groq_api_key", None) and cfg.brain.groq_api_key.strip():
                return cfg.brain.groq_api_key.strip()
        except Exception:
            pass

        # 3. Check environment variable
        env_key = os.environ.get("GROQ_API_KEY", "").strip()
        if env_key:
            return env_key

        return ""

    @property
    def is_configured(self) -> bool:
        """Whether a valid Groq API key is present."""
        return bool(self.get_api_key())

    def set_api_key(self, key: str) -> None:
        """Persist new API key to disk and update active client instance."""
        clean = key.strip()
        self._explicit_key = clean
        KEY_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        KEY_FILE_PATH.write_text(clean, encoding="utf-8")
        logger.info("Groq API key saved to %s", KEY_FILE_PATH)

    def clear_history(self) -> None:
        """Reset conversation memory buffer."""
        self._history.clear()
        logger.info("Groq multi-turn conversation memory cleared.")

    def get_history(self) -> list[dict[str, str]]:
        """Get copy of current conversation history."""
        return list(self._history)

    def chat(self, prompt: str, system_prompt: str = GROQ_SYSTEM_PROMPT) -> str:
        """Send user query to Groq Cloud API with multi-turn memory.

        Args:
            prompt: User utterance or question.
            system_prompt: System persona instruction.

        Returns:
            AI response string.

        Raises:
            GroqAuthError: If no API key is configured.
            GroqClientError: If the request fails or times out.
        """
        key = self.get_api_key()
        if not key:
            raise GroqAuthError("Groq API key is not configured. Please add your key in Settings.")

        # Build messages payload with conversation history
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

        # Append recent history (limited to max_history_turns * 2 messages)
        recent_history = self._history[-(self.max_history_turns * 2):]
        messages.extend(recent_history)

        # Append current user prompt
        messages.append({"role": "user", "content": prompt.strip()})

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.6,
            "max_tokens": 512,
            "top_p": 0.95,
        }

        timeout = httpx.Timeout(self.timeout_sec, connect=5.0)
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(GROQ_ENDPOINT, json=payload, headers=headers)
                if resp.status_code == 401:
                    logger.warning("Groq API returned 401 Unauthorized.")
                    raise GroqAuthError("Invalid Groq API key.")
                if resp.status_code == 404:
                    logger.warning("Groq model '%s' not found (HTTP 404). Trying fallbacks...", self.model)
                    for fb_model in FALLBACK_MODELS:
                        if fb_model == self.model:
                            continue
                        payload["model"] = fb_model
                        fb_resp = client.post(GROQ_ENDPOINT, json=payload, headers=headers)
                        if fb_resp.status_code == 200:
                            logger.info("Successfully switched to Groq fallback model: %s", fb_model)
                            self.model = fb_model
                            resp = fb_resp
                            break

                if resp.status_code != 200:
                    logger.warning("Groq API returned HTTP %d: %s", resp.status_code, resp.text)
                    raise GroqClientError(f"Groq API returned HTTP {resp.status_code}")

                data = resp.json()
                choices = data.get("choices", [])
                if not choices:
                    raise GroqClientError("No response choices returned by Groq.")

                raw_reply = choices[0].get("message", {}).get("content", "").strip()

                # Clean reply: strip any unexpected Arabic unicode so Piper TTS speaks cleanly
                clean_reply = re.sub(r'[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]+', ' ', raw_reply)
                clean_reply = " ".join(clean_reply.split()).strip()
                if not clean_reply:
                    clean_reply = raw_reply

                # Append to multi-turn conversation memory
                self._history.append({"role": "user", "content": prompt.strip()})
                self._history.append({"role": "assistant", "content": clean_reply})

                # Trim memory buffer if exceeded
                if len(self._history) > (self.max_history_turns * 2):
                    self._history = self._history[-(self.max_history_turns * 2):]

                return clean_reply

        except httpx.TimeoutException as e:
            logger.warning("Groq API request timed out: %s", e)
            raise GroqClientError(f"Groq request timed out: {e}") from e
        except (httpx.ConnectError, httpx.HTTPError, OSError) as e:
            logger.warning("Groq network error: %s", e)
            raise GroqClientError(f"Groq network error: {e}") from e
