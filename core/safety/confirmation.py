"""Confirmation Manager for destructive actions.

Security Rule 5:
Destructive actions (delete, shutdown, restart, close-all, overwrite)
ALWAYS need a spoken or button confirmation. No bypass flag.
"""

import time
from collections.abc import Callable

from core.logger import get_logger

logger = get_logger("safety.confirmation")

AFFIRMATIVE_RESPONSES = {"yes", "confirm", "proceed", "sure", "do it", "yep", "yeah"}
NEGATIVE_RESPONSES = {"no", "cancel", "stop", "abort", "don't", "never", "nope"}


class ConfirmationTimeoutError(TimeoutError):
    """Raised when confirmation prompt times out without user approval."""


class ConfirmationManager:
    """Manages spoken and button approvals for destructive actions."""

    def __init__(self, default_timeout_sec: float = 10.0) -> None:
        """Initialize ConfirmationManager.

        Args:
            default_timeout_sec: Seconds to wait before automatically cancelling.
        """
        self.default_timeout_sec = default_timeout_sec

    def request_confirmation(
        self,
        action_name: str,
        prompt: str | None = None,
        timeout_sec: float | None = None,
        voice_pipeline: object | None = None,
        input_provider: Callable[[float], str | None] | None = None,
    ) -> bool:
        """Prompt user for confirmation via voice or input callback.

        Strictly enforces confirmation with NO bypass option (Rule 5).

        Args:
            action_name: Name of destructive action (e.g. 'shutdown', 'restart').
            prompt: Question to ask user.
            timeout_sec: Timeout duration in seconds (defaults to 10.0s).
            voice_pipeline: Optional VoicePipeline to speak prompt and capture response.
            input_provider: Optional callable taking timeout_sec and returning response string.

        Returns:
            True if user explicitly confirmed, False if denied or timed out.
        """
        timeout = timeout_sec or self.default_timeout_sec
        display_prompt = prompt or f"Are you sure you want to perform {action_name}? Please confirm."
        logger.warning("CONFIRMATION REQUIRED for '%s': %s", action_name, display_prompt)

        # 1. Speak prompt if voice pipeline is available
        if voice_pipeline and hasattr(voice_pipeline, "speak"):
            try:
                voice_pipeline.speak(display_prompt)
            except Exception as e:  # noqa: BLE001
                logger.error("Failed to speak confirmation prompt: %s", e)

        # 2. Get user response via input provider or voice listen
        user_response: str | None = None
        t_start = time.perf_counter()

        if input_provider:
            user_response = input_provider(timeout)
        elif voice_pipeline and hasattr(voice_pipeline, "listen"):
            logger.info("Listening for confirmation response (yes/no) for %.1fs...", timeout)
            user_response = voice_pipeline.listen(wait_for_trigger=False, timeout=timeout)

        # 3. Handle timeout / no response
        elapsed = time.perf_counter() - t_start
        if not user_response or elapsed > timeout:
            logger.info("Confirmation for '%s' TIMED OUT after %.1fs. Action cancelled.", action_name, elapsed)
            return False

        # 4. Evaluate response
        clean_resp = user_response.strip().lower()
        if any(aff in clean_resp for aff in AFFIRMATIVE_RESPONSES):
            logger.info("Action '%s' CONFIRMED by user ('%s').", action_name, clean_resp)
            return True

        logger.info("Action '%s' DENIED by user ('%s').", action_name, clean_resp)
        return False
