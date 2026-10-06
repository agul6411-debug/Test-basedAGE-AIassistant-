"""Unit tests for local Ollama LLM fallback client, tool calling, and security guardrails."""

from unittest.mock import MagicMock, patch

import pytest

from core.brain.ollama_client import OFFLINE_MESSAGE, OllamaClient
from core.brain.router import CommandRouter
from core.safety.confirmation import ConfirmationManager

# ==============================================================================
# Security Rule 1: Loopback Verification
# ==============================================================================

def test_ollama_client_rejects_external_ip():
    with pytest.raises(ValueError, match="SECURITY VIOLATION"):
        OllamaClient(base_url="http://192.168.1.100:11434")

    with pytest.raises(ValueError, match="SECURITY VIOLATION"):
        OllamaClient(base_url="http://external-api.com:11434")


def test_ollama_client_accepts_loopback():
    client_ip = OllamaClient(base_url="http://127.0.0.1:11434")
    assert client_ip.base_url == "http://127.0.0.1:11434"

    client_host = OllamaClient(base_url="http://localhost:11434")
    assert client_host.base_url == "http://localhost:11434"


def test_ollama_tool_definitions_export():
    client = OllamaClient()
    tools = client.get_tool_definitions()
    assert len(tools) >= 10
    tool_names = {t["function"]["name"] for t in tools}
    assert "open_app" in tool_names
    assert "set_volume" in tool_names
    assert "shutdown" in tool_names
    for t in tools:
        assert t["type"] == "function"
        assert "parameters" in t["function"]


# ==============================================================================
# Graceful Offline Fallback
# ==============================================================================

def test_ollama_offline_returns_thinking_engine_offline():
    # Point to an unused local port guaranteed to fail connection
    client = OllamaClient(base_url="http://127.0.0.1:59999", timeout_sec=0.5)
    result = client.chat("Explain quantum mechanics")
    assert result.success is False
    assert result.message == OFFLINE_MESSAGE


def test_router_falls_back_to_offline_ollama():
    client = OllamaClient(base_url="http://127.0.0.1:59999", timeout_sec=0.5)
    router = CommandRouter(ollama_client=client)

    # Input that has no Layer 1 rule match
    result = router.execute_command("Why does the moon have craters?")
    assert result.matched is False
    assert result.success is False
    assert result.message == OFFLINE_MESSAGE


# ==============================================================================
# Conversational Replies (No Tool Call)
# ==============================================================================

def test_ollama_conversational_reply():
    client = OllamaClient()
    mock_resp = {
        "model": "qwen2.5:3b",
        "message": {
            "role": "assistant",
            "content": "The sky appears blue due to Rayleigh scattering.",
        },
    }

    with patch.object(client, "_query_ollama", return_value=mock_resp):
        result = client.chat("Why is the sky blue?")
        assert result.success is True
        assert result.message == "The sky appears blue due to Rayleigh scattering."


# ==============================================================================
# Valid Tool Calling
# ==============================================================================

def test_ollama_valid_tool_call_volume():
    client = OllamaClient()
    mock_resp = {
        "model": "qwen2.5:3b",
        "message": {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "set_volume",
                        "arguments": {"level": 50},
                    }
                }
            ],
        },
    }

    with (
        patch.object(client, "_query_ollama", return_value=mock_resp),
        patch("pycaw.pycaw.AudioUtilities") as mock_audio,
    ):
        mock_dev = MagicMock()
        mock_audio.GetSpeakers.return_value = mock_dev
        mock_dev.EndpointVolume.GetMasterVolumeLevelScalar.return_value = 0.3

        result = client.chat("Can you set the volume to 50 percent?")
        assert result.success is True
        assert result.data.get("tool_name") == "set_volume"


# ==============================================================================
# Security Rule 3 & 4: Untrusted LLM Attack & Validation Tests
# ==============================================================================

def test_attack_hallucinated_unregistered_tool():
    client = OllamaClient()
    mock_resp = {
        "model": "qwen2.5:3b",
        "message": {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "execute_bash_command",
                        "arguments": {"cmd": "rm -rf /"},
                    }
                }
            ],
        },
    }

    with patch.object(client, "_query_ollama", return_value=mock_resp):
        result = client.chat("Delete all files on my disk")
        assert result.success is False
        assert "not in the approved tools list" in result.message


def test_attack_disallowed_application_launch():
    client = OllamaClient()
    for bad_app in ["cmd", "cmd.exe", "powershell", "powershell.exe", "bash", "curl"]:
        mock_resp = {
            "model": "qwen2.5:3b",
            "message": {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "open_app",
                            "arguments": {"app_name": bad_app},
                        }
                    }
                ],
            },
        }

        with patch.object(client, "_query_ollama", return_value=mock_resp):
            result = client.chat(f"Open {bad_app}")
            assert result.success is False
            assert "not permitted by allowlist" in result.message


def test_attack_command_injection_in_tool_args():
    client = OllamaClient()
    mock_resp = {
        "model": "qwen2.5:3b",
        "message": {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "open_app",
                        "arguments": {"app_name": "notepad & calc.exe"},
                    }
                }
            ],
        },
    }

    with patch.object(client, "_query_ollama", return_value=mock_resp):
        result = client.chat("Open notepad and calc")
        assert result.success is False
        assert "not permitted by allowlist" in result.message


def test_attack_malformed_json_arguments():
    client = OllamaClient()
    result = client.execute_untrusted_tool(
        tool_name="open_app",
        raw_args="{invalid json here: 123",
    )
    assert result.success is False
    assert "Malformed JSON" in result.message


def test_attack_invalid_schema_types():
    client = OllamaClient()
    # set_volume requires int, not string
    result = client.execute_untrusted_tool(
        tool_name="set_volume",
        raw_args={"level": "maximum_loudness"},
    )
    assert result.success is False
    assert "Invalid arguments" in result.message


def test_attack_out_of_bounds_schema():
    client = OllamaClient()
    # level cannot exceed 100
    result = client.execute_untrusted_tool(
        tool_name="set_volume",
        raw_args={"level": 250},
    )
    assert result.success is False
    assert "Invalid arguments" in result.message


def test_dangerous_tool_confirmation_denied():
    confirm_mgr = ConfirmationManager()
    client = OllamaClient(confirmation_manager=confirm_mgr)

    mock_resp = {
        "model": "qwen2.5:3b",
        "message": {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "shutdown",
                        "arguments": {},
                    }
                }
            ],
        },
    }

    with (
        patch.object(client, "_query_ollama", return_value=mock_resp),
        patch.object(confirm_mgr, "request_confirmation", return_value=False),
    ):
        result = client.chat("Turn off computer")
        assert result.success is False
        assert "was cancelled" in result.message


def test_dangerous_tool_confirmation_granted():
    confirm_mgr = ConfirmationManager()
    client = OllamaClient(confirmation_manager=confirm_mgr)

    mock_resp = {
        "model": "qwen2.5:3b",
        "message": {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "shutdown",
                        "arguments": {},
                    }
                }
            ],
        },
    }

    with (
        patch.object(client, "_query_ollama", return_value=mock_resp),
        patch.object(confirm_mgr, "request_confirmation", return_value=True),
        patch("core.safety.process_runner.SafeProcessRunner.run_command") as mock_proc,
    ):
        mock_proc.return_value = MagicMock(returncode=0)
        result = client.chat("Turn off computer")
        assert result.success is True
        assert "shutdown initiated" in result.message.lower()
