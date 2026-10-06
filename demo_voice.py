"""AGE Voice Pipeline & Command Router Demonstration Script.

Say a voice command (or trigger via Ctrl+Space), AGE transcribes it,
routes it through Layer 1 tools, executes the action, and speaks the reply.
"""

import time

from core.brain.router import CommandRouter
from core.logger import setup_logger
from core.safety.action_logger import ActionLogger
from core.safety.confirmation import ConfirmationManager
from core.voice.pipeline import VoicePipeline


def main() -> None:
    """Run interactive voice-controlled assistant demonstration."""
    logger = setup_logger(log_file="age.log", log_level="INFO")
    logger.info("Initializing AGE Voice & Router Demo...")

    print("=" * 60)
    print("   AGE - Voice Assistant & Tool Router Demo (Phase 3)")
    print("=" * 60)
    print("Example commands to try:")
    print("  • \"open notepad\"")
    print("  • \"volume up\"  or  \"set volume to 40\"")
    print("  • \"search YouTube for cooking videos\"")
    print("  • \"search web for python 3.11\"")
    print("  • \"lock the screen\"")
    print("  • \"close notepad\"")
    print("  • \"shutdown\" (will request confirmation!)")
    print("\nPress Ctrl+C to exit.\n")

    pipeline = VoicePipeline(auto_download_models=True)
    confirmation_mgr = ConfirmationManager(default_timeout_sec=8.0)
    action_logger = ActionLogger()
    router = CommandRouter(confirmation_manager=confirmation_mgr, action_logger=action_logger)

    try:
        while True:
            print("-" * 60)
            print("Listening for wake word or Ctrl+Space backup hotkey...")
            t_cycle_start = time.perf_counter()

            transcript = pipeline.listen(wait_for_trigger=True)

            if not transcript:
                print("No speech detected. Listening again...")
                continue

            cycle_latency = time.perf_counter() - t_cycle_start
            print(f"\n[TRANSCRIPT] \"{transcript}\" (latency: {cycle_latency:.2f}s)")

            # Route and execute command
            result = router.execute_command(transcript, voice_pipeline=pipeline)
            print(f"[ACTION] Tool: {result.tool_name} | Success: {result.success} | Message: {result.message}")

            # Speak response back to user
            pipeline.speak(result.message)
            print("[DONE] Cycle completed.\n")

    except KeyboardInterrupt:
        print("\nExiting voice assistant demo. Goodbye!")
    finally:
        pipeline.close()


if __name__ == "__main__":
    main()
