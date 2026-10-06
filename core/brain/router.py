"""Layer 1 Rule and Keyword Command Router.

Security Rule 3:
LLM and transcribed speech are untrusted input.
All parameters are sanitized and strictly validated against Pydantic schemas.
"""

import re
from typing import Any

from pydantic import BaseModel, Field

from core.brain.ollama_client import OFFLINE_MESSAGE, OllamaClient
from core.logger import get_logger
from core.safety.action_logger import ActionLogger
from core.safety.confirmation import ConfirmationManager
from core.tools.registry import registry

logger = get_logger("brain.router")

MAX_INPUT_LENGTH = 1000


class CommandResult(BaseModel):
    """Result of router matching and command dispatch."""
    matched: bool
    success: bool = False
    message: str = ""
    tool_name: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class CommandRouter:
    """Layer 1 pattern and regex intent router."""

    def __init__(
        self,
        confirmation_manager: ConfirmationManager | None = None,
        action_logger: ActionLogger | None = None,
        ollama_client: OllamaClient | None = None,
        enable_llm_fallback: bool = True,
    ) -> None:
        """Initialize CommandRouter.

        Args:
            confirmation_manager: Manager for confirming dangerous actions (Rule 5).
            action_logger: Action audit logger (Rule 12).
            ollama_client: Optional Ollama client for Layer 2 fallback.
            enable_llm_fallback: Whether to instantiate OllamaClient if not provided.
        """
        self.confirmation_manager = confirmation_manager or ConfirmationManager()
        self.action_logger = action_logger or ActionLogger()
        if ollama_client is not None:
            self.ollama_client = ollama_client
        elif enable_llm_fallback:
            self.ollama_client = OllamaClient(
                confirmation_manager=self.confirmation_manager,
                action_logger=self.action_logger,
            )
        else:
            self.ollama_client = None

    def sanitize_input(self, raw_text: str) -> str:
        """Sanitize raw transcribed speech or user input.

        Args:
            raw_text: Untrusted speech string.

        Returns:
            Sanitized, lowercased string truncated to safe length.
        """
        if not raw_text or not isinstance(raw_text, str):
            return ""

        # Limit length to prevent regex DoS
        truncated = raw_text[:MAX_INPUT_LENGTH]

        # Strip null bytes and control characters
        cleaned = re.sub(r'[\x00-\x1f\x7f]', ' ', truncated)

        # Normalize whitespace and lowercase
        return " ".join(cleaned.strip().split()).lower()

    def route_intent(self, text: str) -> tuple[str, dict[str, Any]] | None:
        """Classify input text into (tool_name, tool_params).

        Args:
            text: Sanitized input command.

        Returns:
            Tuple of (tool_name, params) or None if no rule matches.
        """
        if not text:
            return None

        # 1. Close all windows
        if re.search(r'^(?:close|quit|exit)\s+all(?:\s+windows|\s+apps|\s+applications)?$', text):
            return "close_all", {}

        # 2. Open App
        m_open = re.search(r'^(?:open|launch|start|run)\s+(?:the\s+)?([a-z0-9_\-\s]+)$', text)
        if m_open:
            app_raw = m_open.group(1).strip()
            # Guard against chained commands or injection operators
            if not re.search(r'[;&|><]', app_raw):
                return "open_app", {"app_name": app_raw}

        # 3. Close App
        m_close = re.search(r'^(?:close|quit|exit|terminate|kill)\s+(?:the\s+)?([a-z0-9_\-\s]+)$', text)
        if m_close:
            app_raw = m_close.group(1).strip()
            if not re.search(r'[;&|><]', app_raw):
                return "close_app", {"app_name": app_raw}

        # 4. Volume Controls
        if re.search(r'^(?:turn\s+)?volume\s+up$', text) or text == "louder":
            return "set_volume", {"delta": 10}
        if re.search(r'^(?:turn\s+)?volume\s+down$', text) or text == "quieter":
            return "set_volume", {"delta": -10}

        m_vol_level = re.search(r'^(?:set\s+)?volume\s+(?:to\s+)?(\d{1,3})(?:%|\s*percent)?$', text)
        if m_vol_level:
            level = int(m_vol_level.group(1))
            if 0 <= level <= 100:
                return "set_volume", {"level": level}

        if text in ("mute", "mute volume", "mute audio", "mute sound"):
            return "set_volume", {"mute": True}
        if text in ("unmute", "unmute volume", "unmute audio", "unmute sound"):
            return "set_volume", {"mute": False}

        # 5. Brightness Controls
        if re.search(r'^(?:turn\s+)?brightness\s+up$', text):
            return "set_brightness", {"delta": 10}
        if re.search(r'^(?:turn\s+)?brightness\s+down$', text):
            return "set_brightness", {"delta": -10}

        m_bright_level = re.search(r'^(?:set\s+)?brightness\s+(?:to\s+)?(\d{1,3})(?:%|\s*percent)?$', text)
        if m_bright_level:
            level = int(m_bright_level.group(1))
            if 0 <= level <= 100:
                return "set_brightness", {"level": level}

        # 6. Lock Screen
        if re.search(r'^(?:lock|lock\s+the|lock\s+my)\s+(?:screen|pc|computer|workstation|desktop)$', text) or text == "lock":
            return "lock_screen", {}

        # 7. YouTube Search (check before generic web search)
        m_yt = re.search(r'^(?:search\s+youtube\s+for|find\s+on\s+youtube|play\s+on\s+youtube|youtube\s+search\s+for)\s+(.+)$', text)
        if m_yt:
            query = m_yt.group(1).strip()
            return "youtube_search", {"query": query}

        m_yt_play = re.search(r'^(?:play|find)\s+(.+)\s+on\s+youtube$', text)
        if m_yt_play:
            query = m_yt_play.group(1).strip()
            return "youtube_search", {"query": query}

        # 8. Web Search
        m_web = re.search(r'^(?:search\s+(?:the\s+)?(?:web|google|internet)\s+for|search\s+for|google)\s+(.+)$', text)
        if m_web:
            query = m_web.group(1).strip()
            return "web_search", {"query": query}

        # 9. Type Text
        m_type = re.search(r'^(?:type|type\s+text|enter\s+text)\s+(.+)$', text)
        if m_type:
            content = m_type.group(1)
            return "type_text", {"text": content}

        # 10. System Shutdown (Dangerous)
        if re.search(r'^(?:shut\s*down|turn\s*off)\s+(?:the\s+)?(?:pc|computer|system|laptop)$', text) or text == "shutdown":
            return "shutdown", {}

        # 11. System Restart (Dangerous)
        if re.search(r'^(?:restart|reboot)\s+(?:the\s+)?(?:pc|computer|system|laptop)$', text) or text in ("restart", "reboot"):
            return "restart", {}

        return None

    def execute_command(
        self,
        raw_input: str,
        voice_pipeline: Any | None = None,
        force_confirmed: bool = False,
    ) -> CommandResult:
        """Route and execute command with security checks and confirmations.

        Args:
            raw_input: Raw spoken or typed command.
            voice_pipeline: Optional VoicePipeline for spoken confirmations.
            force_confirmed: Internal testing override flag for simulation.

        Returns:
            CommandResult.
        """
        clean_text = self.sanitize_input(raw_input)
        if not clean_text:
            return CommandResult(matched=False, message="Input is empty.")

        intent = self.route_intent(clean_text)
        if not intent:
            logger.info("No Layer 1 rule matched for input: '%s'", clean_text)
            if self.ollama_client:
                logger.info("Falling back to Layer 2 Ollama LLM...")
                llm_res = self.ollama_client.chat(
                    prompt=clean_text,
                    voice_pipeline=voice_pipeline,
                    force_confirmed=force_confirmed,
                )
                if not llm_res.success and llm_res.message == OFFLINE_MESSAGE:
                    return CommandResult(
                        matched=False,
                        success=False,
                        message=OFFLINE_MESSAGE,
                    )
                return CommandResult(
                    matched=True,
                    success=llm_res.success,
                    message=llm_res.message,
                    tool_name=llm_res.data.get("tool_name"),
                    data=llm_res.data,
                )

            return CommandResult(
                matched=False,
                message=f"I didn't recognize the command: '{clean_text}'.",
            )

        tool_name, params = intent
        tool = registry.get(tool_name)
        if not tool:
            return CommandResult(
                matched=True,
                success=False,
                message=f"Tool '{tool_name}' is not registered.",
                tool_name=tool_name,
            )

        # Security Rule 5: Dangerous actions ALWAYS require confirmation
        if tool.is_dangerous:
            confirmed = force_confirmed or self.confirmation_manager.request_confirmation(
                action_name=tool_name,
                prompt=f"Are you sure you want to {tool_name}? Please say yes or no.",
                voice_pipeline=voice_pipeline,
            )
            if not confirmed:
                msg = f"Action '{tool_name}' was cancelled."
                self.action_logger.log(tool_name, params, msg, success=False)
                return CommandResult(
                    matched=True,
                    success=False,
                    message=msg,
                    tool_name=tool_name,
                )

        # Execute tool via strict Pydantic validation
        result = tool.run(**params)

        # Security Rule 12: Audit action execution
        self.action_logger.log(tool_name, params, result.message, success=result.success)

        return CommandResult(
            matched=True,
            success=result.success,
            message=result.message,
            tool_name=tool_name,
            data=result.data,
        )
