"""Unit tests for offline voice pipeline logic."""

from pathlib import Path

import numpy as np
import pytest

from core.voice.hotkey import HotkeyTrigger
from core.voice.model_downloader import (
    MODEL_REGISTRY,
    compute_file_sha256,
)
from core.voice.stt import SpeechToText
from core.voice.tts import TextToSpeech
from core.voice.vad import SileroVAD, SpeechEndpointDetector
from core.voice.wake_word import WakeWordDetector


def test_compute_file_sha256(tmp_path: Path):
    test_file = tmp_path / "sample.bin"
    test_file.write_bytes(b"hello world")
    # echo -n "hello world" | sha256sum -> b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9
    expected = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    assert compute_file_sha256(test_file) == expected


def test_model_registry_entries():
    assert "silero_vad.onnx" in MODEL_REGISTRY
    assert "en_US-lessac-medium.onnx" in MODEL_REGISTRY
    assert "en_US-lessac-medium.onnx.json" in MODEL_REGISTRY


def test_silero_vad_silence_detection():
    vad = SileroVAD()
    silence_frame = np.zeros(512, dtype=np.int16)
    prob = vad.process_frame(silence_frame)
    assert isinstance(prob, float)
    assert 0.0 <= prob <= 0.1  # Silence probability must be near zero
    assert not vad.is_speech(silence_frame, threshold=0.5)


def test_silero_vad_rejects_invalid_size():
    vad = SileroVAD()
    invalid_frame = np.zeros(256, dtype=np.int16)
    with pytest.raises(ValueError, match="512 samples"):
        vad.process_frame(invalid_frame)


def test_speech_endpoint_detector_silence_cutoff():
    vad = SileroVAD()
    detector = SpeechEndpointDetector(
        vad=vad,
        speech_threshold=0.5,
        silence_duration_sec=0.1,  # short silence duration for fast test
        frame_size=512,
    )

    # Sequence: 10 frames of silence
    frames = [np.zeros(512, dtype=np.int16) for _ in range(10)]
    recorded = detector.record_until_silence(iter(frames))
    assert isinstance(recorded, np.ndarray)


def test_hotkey_trigger_programmatic():
    trigger = HotkeyTrigger()
    assert not trigger.is_triggered

    trigger.trigger()
    assert trigger.wait(timeout=0.5) is True
    # After wait, event should auto-clear
    assert not trigger.is_triggered


def test_wake_word_detector_fallback_on_empty_key(monkeypatch):
    monkeypatch.setenv("PORCUPINE_ACCESS_KEY", "")
    detector = WakeWordDetector()
    assert detector.is_available is False
    # process_frame should safely return False without error
    pcm = np.zeros(512, dtype=np.int16)
    assert detector.process_frame(pcm) is False
    detector.close()


def test_tts_synthesize_memory():
    tts = TextToSpeech()
    # Empty text
    empty_audio, sr = tts.synthesize("")
    assert len(empty_audio) == 0

    # Real text synthesis in RAM
    audio, sr = tts.synthesize("Hi")
    assert isinstance(audio, np.ndarray)
    assert len(audio) > 0
    assert audio.dtype == np.int16
    assert sr == 22050


def test_stt_transcribe_empty():
    stt = SpeechToText()
    result = stt.transcribe(np.array([], dtype=np.int16))
    assert result == ""
