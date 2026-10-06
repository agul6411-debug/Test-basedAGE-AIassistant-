"""AGE Voice Pipeline Demonstration Script.

Say a sentence (or trigger via Ctrl+Space), prints the text with latency breakdown,
and speaks it back via Piper TTS.
"""

import time

from core.logger import setup_logger
from core.voice.pipeline import VoicePipeline


def main() -> None:
    """Run interactive voice pipeline demonstration."""
    logger = setup_logger(log_file="age.log", log_level="INFO")
    logger.info("Initializing AGE Voice Pipeline Demo...")

    print("=" * 60)
    print("   AGE - MY BEST FRIEND AI Voice Pipeline Demo")
    print("=" * 60)
    print("Instructions:")
    print("  1. Say the wake word (or press Ctrl+Space).")
    print("  2. Speak your English sentence clearly.")
    print("  3. Pause when finished; Silero VAD will detect the end of speech.")
    print("  4. Faster-Whisper will transcribe it, and Piper TTS will speak it back.")
    print("  Press Ctrl+C to exit.\n")

    pipeline = VoicePipeline(auto_download_models=True)

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
            print(f"\n[TRANSCRIPT] \"{transcript}\"")
            print(f"[TIMING] Total round-trip latency: {cycle_latency:.2f}s\n")

            reply = f"You said: {transcript}"
            print(f"[REPLY] Speaking: \"{reply}\"...")
            pipeline.speak(reply)
            print("[DONE] Speech playback complete.\n")

    except KeyboardInterrupt:
        print("\nExiting voice demo. Goodbye!")
    finally:
        pipeline.close()


if __name__ == "__main__":
    main()
