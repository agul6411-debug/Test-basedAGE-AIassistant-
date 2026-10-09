"""Unit tests for Groq Cloud API Client and Multi-Turn Memory."""

import pytest
from unittest.mock import MagicMock, patch
import httpx

from core.brain.groq_client import (
    GroqAuthError,
    GroqClient,
    GroqClientError,
    KEY_FILE_PATH,
)


@pytest.fixture
def clean_groq_key(tmp_path):
    """Ensure key file doesn't pollute during testing."""
    test_key_file = tmp_path / "test_groq_key.txt"
    with patch("core.brain.groq_client.KEY_FILE_PATH", test_key_file):
        yield test_key_file


def test_groq_client_init():
    client = GroqClient(api_key="gsk_test123", model="llama-3.3-70b-versatile")
    assert client.get_api_key() == "gsk_test123"
    assert client.is_configured is True
    assert client.model == "llama-3.3-70b-versatile"
    assert client.get_history() == []


def test_groq_set_key_and_clear_history(clean_groq_key):
    client = GroqClient()
    assert client.is_configured is False

    client.set_api_key("gsk_new_secret_key")
    assert client.get_api_key() == "gsk_new_secret_key"
    assert client.is_configured is True
    assert clean_groq_key.read_text(encoding="utf-8").strip() == "gsk_new_secret_key"

    client._history.append({"role": "user", "content": "hi"})
    client._history.append({"role": "assistant", "content": "hello"})
    assert len(client.get_history()) == 2

    client.clear_history()
    assert client.get_history() == []


def test_groq_chat_without_key_raises_auth_error():
    client = GroqClient(api_key="")
    with patch.object(client, "get_api_key", return_value=""):
        with pytest.raises(GroqAuthError):
            client.chat("Hello there")


def test_groq_chat_success_and_multi_turn_history():
    client = GroqClient(api_key="gsk_valid_key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Hello! I am doing great, how can I assist you today?",
                }
            }
        ]
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        reply = client.chat("Hi, how are you?")
        assert "Hello!" in reply
        history = client.get_history()
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "Hi, how are you?"}
        assert history[1] == {"role": "assistant", "content": reply}


def test_groq_chat_strips_arabic_script():
    client = GroqClient(api_key="gsk_valid_key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Main bilkul theek hoon! میں آپ کی مدد کر سکتا ہوں",
                }
            }
        ]
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        reply = client.chat("kese ho?")
        # Perso-Arabic chars should be cleaned
        assert "میں" not in reply
        assert "Main bilkul theek hoon!" in reply


def test_groq_chat_401_raises_auth_error():
    client = GroqClient(api_key="gsk_invalid_key")

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "Unauthorized"

    with patch("httpx.Client.post", return_value=mock_resp):
        with pytest.raises(GroqAuthError):
            client.chat("Hello")


def test_groq_chat_timeout_raises_client_error():
    client = GroqClient(api_key="gsk_valid_key")

    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("Timeout")):
        with pytest.raises(GroqClientError):
            client.chat("Hello")
