"""Offline voice pipeline package for AGE - MY BEST FRIEND AI."""

from core.voice.audio_capture import AudioCapture
from core.voice.hotkey import HotkeyTrigger
from core.voice.model_downloader import ensure_voice_models
from core.voice.pipeline import VoicePipeline
from core.voice.stt import SpeechToText
from core.voice.tts import TextToSpeech
from core.voice.vad import SileroVAD, SpeechEndpointDetector
from core.voice.wake_word import WakeWordDetector

__all__ = [
    "AudioCapture",
    "HotkeyTrigger",
    "SileroVAD",
    "SpeechEndpointDetector",
    "SpeechToText",
    "TextToSpeech",
    "VoicePipeline",
    "WakeWordDetector",
    "ensure_voice_models",
]
