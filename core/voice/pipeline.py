"""Unified offline voice pipeline for AGE.

Exposes clean interface: listen() -> text, speak(text).
All audio processing is strictly in-memory (Security Rule 7).
Transcribed text is untrusted input (Security Rule 3).
"""

import time
from collections import deque
from collections.abc import Generator

import numpy as np

from core.logger import get_logger
from core.voice.audio_capture import AudioCapture
from core.voice.hotkey import HotkeyTrigger
from core.voice.model_downloader import ensure_voice_models
from core.voice.stt import SpeechToText
from core.voice.tts import TextToSpeech
from core.voice.vad import SileroVAD, SpeechEndpointDetector
from core.voice.wake_word import WakeWordDetector

logger = get_logger("voice.pipeline")


class VoicePipeline:
    """Unified voice orchestrator providing listen() and speak() interfaces."""

    def __init__(
        self,
        auto_download_models: bool = True,
    ) -> None:
        """Initialize VoicePipeline and required models.

        Args:
            auto_download_models: If True, verifies/downloads models on startup.
        """
        logger.info("Initializing VoicePipeline...")
        if auto_download_models:
            ensure_voice_models()

        self.capture = AudioCapture(sample_rate=16000, frame_size=512)
        self.hotkey = HotkeyTrigger()
        self.wake_detector = WakeWordDetector()
        self.vad = SileroVAD()
        self.endpoint_detector = SpeechEndpointDetector(vad=self.vad)
        self.stt = SpeechToText()
        self.tts = TextToSpeech()
        logger.info("VoicePipeline initialized successfully.")

    def _frame_generator(self) -> Generator[np.ndarray | None, None, None]:
        """Yield frames continuously from the audio capture stream."""
        while self.capture.is_active:
            frame = self.capture.read_frame(timeout=0.2)
            if frame is not None:
                yield frame

    def listen(self, wait_for_trigger: bool = True, timeout: float | None = None) -> str:
        """Listen for speech and return transcribed text.

        Args:
            wait_for_trigger: If True, waits for wake word or Ctrl+Space before recording.
            timeout: Optional maximum seconds to wait for wake word trigger.

        Returns:
            Transcribed speech text (untrusted input).
        """
        self.capture.start()
        self.hotkey.start()
        trigger_type = "direct"
        t_trigger_start = time.perf_counter()
        pre_roll_buffer: deque[np.ndarray] = deque(maxlen=20)

        try:
            if wait_for_trigger:
                logger.info(
                    "Listening for wake word ('%s') or Ctrl+Space backup hotkey...",
                    self.wake_detector.keyword,
                )
                detected = False

                while True:
                    if timeout and (time.perf_counter() - t_trigger_start > timeout):
                        logger.info("Listen timed out waiting for trigger.")
                        return ""

                    # Check backup hotkey
                    if self.hotkey.is_triggered:
                        trigger_type = "hotkey (Ctrl+Space)"
                        detected = True
                        break

                    # Check audio wake word or auto voice activity
                    frame = self.capture.read_frame(timeout=0.05)
                    if frame is not None:
                        pre_roll_buffer.append(frame)
                        if (
                            self.wake_detector.is_available
                            and self.wake_detector.process_frame(frame)
                        ):
                            trigger_type = f"wake_word ({self.wake_detector.keyword})"
                            detected = True
                            break
                        elif not self.wake_detector.is_available:
                            # Automatic voice detection when Porcupine key is absent
                            prob = self.vad.process_frame(frame)
                            if prob >= 0.38:
                                trigger_type = "voice (Silero VAD)"
                                detected = True
                                break

                if not detected:
                    return ""

            trigger_latency = time.perf_counter() - t_trigger_start
            print(f"\n🎤 [{trigger_type.upper()}] Active! Speak your command now...")
            logger.info(">>> Triggered via %s in %.3fs. Recording speech...", trigger_type, trigger_latency)

            # Record speech until Silero VAD detects end of speech, prepending pre-roll buffer
            t_rec_start = time.perf_counter()
            initial_frames = list(pre_roll_buffer) if trigger_type.startswith("voice") else []
            audio_data = self.endpoint_detector.record_until_silence(
                self._frame_generator(),
                initial_frames=initial_frames,
                speech_already_started=bool(initial_frames),
            )
            rec_duration = time.perf_counter() - t_rec_start

            if len(audio_data) == 0:
                print("   [No speech detected. Returning to standby...]")
                logger.warning("No speech captured.")
                return ""

            print("   [Speech recorded! Transcribing with Whisper...]")

            # Transcribe with faster-whisper
            t_stt_start = time.perf_counter()
            transcript = self.stt.transcribe(audio_data)
            stt_latency = time.perf_counter() - t_stt_start

            total_latency = trigger_latency + rec_duration + stt_latency
            logger.info(
                "[LATENCY REPORT] Trigger: %.3fs | Rec: %.3fs | STT: %.3fs | Total: %.3fs",
                trigger_latency,
                rec_duration,
                stt_latency,
                total_latency,
            )

            return transcript

        finally:
            self.hotkey.stop()
            self.capture.stop()

    def stop(self) -> None:
        """Immediately stop any active speech playback."""
        self.tts.stop()

    def speak(self, text: str, interruptible: bool = True) -> bool:
        """Speak response text using Piper TTS with barge-in interruption support.

        Args:
            text: Text to speak.
            interruptible: If True, checks for user interruption during speech.

        Returns:
            True if completed normally, False if interrupted by user.
        """
        if not text or not text.strip():
            return True

        was_capture_active = getattr(self.capture, "is_active", False)
        was_hotkey_running = getattr(self.hotkey, "is_running", False)

        if interruptible:
            if not was_hotkey_running:
                try:
                    self.hotkey.start()
                except Exception as e:
                    logger.debug("Could not start hotkey during speak: %s", e)
            if not was_capture_active:
                try:
                    self.capture.start()
                except Exception as e:
                    logger.debug("Could not start capture during speak: %s", e)

        def check_interruption() -> bool:
            if self.hotkey.is_triggered:
                return True
            if self.capture.is_active:
                frame = self.capture.read_frame(timeout=0.01)
                if frame is not None:
                    prob = self.vad.process_frame(frame)
                    if prob >= 0.85:
                        return True
            return False

        try:
            checker = check_interruption if interruptible else None
            return self.tts.speak(text, interrupt_check=checker)
        finally:
            if interruptible:
                if not was_capture_active and getattr(self.capture, "is_active", False):
                    try:
                        self.capture.stop()
                    except Exception as e:
                        logger.debug("Could not stop capture after speak: %s", e)
                if not was_hotkey_running and getattr(self.hotkey, "is_running", False):
                    try:
                        self.hotkey.stop()
                    except Exception as e:
                        logger.debug("Could not stop hotkey after speak: %s", e)


    def close(self) -> None:
        """Clean up audio streams, hotkey listeners, and native detectors."""
        self.capture.stop()
        self.hotkey.stop()
        self.wake_detector.close()
