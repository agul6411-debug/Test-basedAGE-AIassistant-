"""Local Ollama client with tool calling and strict untrusted output validation.

Security Rule 1: Connects to localhost loopback ONLY (127.0.0.1:11434).
Security Rule 3: LLM output is UNTRUSTED. Tool calls from the LLM must be
validated against an allowlist and a strict schema (Pydantic) before running.
Security Rule 5: Destructive actions ALWAYS need spoken or button confirmation.
"""

import json
from typing import Any

import httpx
from pydantic import ValidationError

from core.logger import get_logger
from core.safety.action_logger import ActionLogger
from core.safety.confirmation import ConfirmationManager
from core.tools.base import BaseTool, ToolResult
from core.tools.open_app import ALLOWED_APPLICATIONS
from core.tools.registry import registry

logger = get_logger("brain.ollama")

SYSTEM_PROMPT = "Your name is AGE, a helpful offline assistant. Reply briefly. Use tools only from the provided list."
OFFLINE_MESSAGE = "My thinking engine is offline."


class OllamaClientError(Exception):
    """Base exception for Ollama client errors."""


class OllamaOfflineError(OllamaClientError):
    """Raised when local Ollama server is unreachable or offline."""


class OllamaClient:
    """Offline LLM client communicating with local Ollama service."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "qwen2.5:3b",
        keep_alive: str = "15m",
        timeout_sec: float = 15.0,
        confirmation_manager: ConfirmationManager | None = None,
        action_logger: ActionLogger | None = None,
    ) -> None:
        """Initialize Ollama client.

        Args:
            base_url: Ollama HTTP base URL (must be localhost).
            model: Model tag to invoke (default: qwen2.5:3b).
            keep_alive: Duration to keep model in memory (default: 15m).
            timeout_sec: Maximum timeout for HTTP requests.
            confirmation_manager: Safety confirmation manager for dangerous tools.
            action_logger: Audit logger for action execution.
        """
        # Security Rule 1 & 7: Loopback validation
        clean_url = base_url.strip().lower()
        if not clean_url.startswith(("http://127.0.0.1", "http://localhost")):
            raise ValueError(f"SECURITY VIOLATION: Ollama base URL must be loopback only, got '{base_url}'.")

        self.base_url = base_url.rstrip("/")
        self.model = model
        self.keep_alive = keep_alive
        self.timeout_sec = timeout_sec
        self.confirmation_manager = confirmation_manager or ConfirmationManager()
        self.action_logger = action_logger or ActionLogger()

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Export all registered tools as Ollama function calling specifications."""
        tools_list: list[dict[str, Any]] = []
        for tool in registry.list_tools():
            schema = tool.args_schema.model_json_schema()
            tools_list.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": schema.get("properties", {}),
                        "required": schema.get("required", []),
                    },
                },
            })
        return tools_list

    def _query_ollama(
        self,
        prompt: str,
        system_prompt: str = SYSTEM_PROMPT,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send chat request to local Ollama /api/chat endpoint.

        Args:
            prompt: User speech or question.
            system_prompt: System instruction prompt.
            tools: Tool definitions available for function calling.

        Returns:
            Ollama response dictionary.

        Raises:
            OllamaOfflineError: If Ollama service is unreachable or times out.
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "keep_alive": self.keep_alive,
        }
        if tools:
            payload["tools"] = tools

        url = f"{self.base_url}/api/chat"
        timeout_config = httpx.Timeout(self.timeout_sec, connect=2.0)
        try:
            with httpx.Client(timeout=timeout_config) as client:
                resp = client.post(url, json=payload, timeout=timeout_config)
                if resp.status_code != 200:
                    logger.warning("Ollama returned HTTP status %d: %s", resp.status_code, resp.text)
                    raise OllamaOfflineError(f"Ollama returned HTTP {resp.status_code}")
                return resp.json()
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError, OSError) as e:
            logger.warning("Ollama connection failed: %s", e)
            raise OllamaOfflineError(f"Ollama server unavailable: {e}") from e

    def execute_untrusted_tool(
        self,
        tool_name: str,
        raw_args: dict[str, Any] | str,
        voice_pipeline: object | None = None,
        force_confirmed: bool = False,
    ) -> ToolResult:
        """Validate and execute a tool call from untrusted LLM output.

        Security Rule 3: LLM output is UNTRUSTED. Tool calls from the LLM must be
        validated against an allowlist and a strict schema (Pydantic) before running.

        Args:
            tool_name: Name of tool requested by LLM.
            raw_args: Raw arguments dictionary or JSON string.
            voice_pipeline: Optional voice pipeline for dangerous tool confirmations.
            force_confirmed: If True, bypass confirmation prompt (for testing).

        Returns:
            ToolResult containing execution success and response message.
        """
        # 1. Parse arguments if passed as JSON string
        args_dict: dict[str, Any] = {}
        if isinstance(raw_args, str):
            try:
                parsed = json.loads(raw_args)
                if isinstance(parsed, dict):
                    args_dict = parsed
                else:
                    return ToolResult(
                        success=False,
                        message=f"LLM tool arguments must be a dictionary, got {type(parsed).__name__}.",
                    )
            except json.JSONDecodeError as err:
                return ToolResult(
                    success=False,
                    message=f"Malformed JSON arguments from LLM: {err}",
                )
        elif isinstance(raw_args, dict):
            args_dict = raw_args
        else:
            return ToolResult(
                success=False,
                message=f"Invalid arguments type from LLM: {type(raw_args).__name__}.",
            )

        # 2. Allowlist Check: Verify tool exists in registry
        tool: BaseTool | None = registry.get(tool_name)
        if not tool:
            logger.warning("Untrusted LLM attempted unapproved tool '%s'", tool_name)
            self.action_logger.log(
                action=f"rejected_llm_tool_{tool_name}",
                parameters=args_dict,
                result="Rejected unapproved tool call from LLM.",
                success=False,
            )
            return ToolResult(
                success=False,
                message=f"Tool '{tool_name}' is not in the approved tools list.",
            )

        # 3. Schema Validation: Validate parameters against tool's Pydantic schema
        try:
            validated_args = tool.args_schema.model_validate(args_dict)
            clean_params = validated_args.model_dump()
        except ValidationError as err:
            logger.warning("Untrusted LLM tool '%s' failed schema validation: %s", tool_name, err)
            self.action_logger.log(
                action=tool_name,
                parameters=args_dict,
                result=f"Schema validation failed: {err}",
                success=False,
            )
            return ToolResult(
                success=False,
                message=f"Invalid arguments for tool '{tool_name}'.",
            )

        # 4. App Allowlist Check for app-launching tools (Security Rule 4)
        if tool_name in ("open_app", "close_app") and "app_name" in clean_params:
            app_req = clean_params["app_name"].lower().strip()
            if app_req not in ALLOWED_APPLICATIONS:
                logger.warning("Untrusted LLM requested disallowed app '%s'", app_req)
                self.action_logger.log(
                    action=tool_name,
                    parameters=clean_params,
                    result=f"Disallowed app '{app_req}' rejected.",
                    success=False,
                )
                return ToolResult(
                    success=False,
                    message=f"Application '{app_req}' is not permitted by allowlist.",
                )

        # 5. Dangerous Action Confirmation (Security Rule 5)
        if tool.is_dangerous:
            confirmed = force_confirmed or self.confirmation_manager.request_confirmation(
                action_name=tool_name,
                prompt=f"Are you sure you want to {tool_name}? Please say yes or no.",
                voice_pipeline=voice_pipeline,
            )
            if not confirmed:
                logger.info("Dangerous tool '%s' cancelled by user or timed out.", tool_name)
                self.action_logger.log(
                    action=tool_name,
                    parameters=clean_params,
                    result=f"Action '{tool_name}' cancelled by user.",
                    success=False,
                )
                return ToolResult(
                    success=False,
                    message=f"Action '{tool_name}' was cancelled.",
                )

        # 6. Execute tool safely
        result = tool.run(**clean_params)
        if "tool_name" not in result.data:
            result.data["tool_name"] = tool_name

        # 7. Audit log action execution (Security Rule 12)
        self.action_logger.log(
            action=tool_name,
            parameters=clean_params,
            result=result.message,
            success=result.success,
        )

        return result

    def chat(
        self,
        prompt: str,
        voice_pipeline: object | None = None,
        force_confirmed: bool = False,
    ) -> ToolResult:
        """Process user query through local Ollama LLM with tool calling.

        Args:
            prompt: User utterance.
            voice_pipeline: Optional voice pipeline for spoken confirmation.
            force_confirmed: Test flag to bypass interactive confirmation.

        Returns:
            ToolResult with response text or tool result message.
        """
        tools = self.get_tool_definitions()

        try:
            response = self._query_ollama(prompt=prompt, tools=tools)
        except OllamaOfflineError:
            logger.info("Ollama is offline. Returning graceful fallback message.")
            return ToolResult(
                success=False,
                message=OFFLINE_MESSAGE,
            )

        # Parse message response
        message = response.get("message", {})
        tool_calls = message.get("tool_calls", [])

        # Case 1: LLM generated a tool call
        if tool_calls and isinstance(tool_calls, list):
            first_call = tool_calls[0]
            func = first_call.get("function", {})
            tool_name = func.get("name", "")
            tool_args = func.get("arguments", {})

            logger.info("LLM requested tool call: %s(args=%s)", tool_name, tool_args)
            return self.execute_untrusted_tool(
                tool_name=tool_name,
                raw_args=tool_args,
                voice_pipeline=voice_pipeline,
                force_confirmed=force_confirmed,
            )

        # Case 2: LLM generated a conversational reply
        text_content = message.get("content", "").strip()
        if text_content:
            return ToolResult(
                success=True,
                message=text_content,
            )

        return ToolResult(
            success=False,
            message="No response from thinking engine.",
        )
