"""Unit tests for Core WebSocket Server and Protocol.

Security Rules Tested:
- Rule 1: Binds to 127.0.0.1 ONLY, never 0.0.0.0 or wildcard.
- Rule 1: Per-session auth token required; wrong token refused.
- Rule 1: Origin header validation.
- Rule 3: Strict Pydantic schema validation on all incoming frames.
- Rule 5: Dangerous actions require confirmation.
- Rule 10: Instant emergency stop halts actions.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from core.brain.router import CommandRouter
from core.config import AppConfig, ServerConfig
from core.safety.token_manager import SessionTokenManager
from core.server.protocol import (
    AuthRequest,
    ExecuteCommandRequest,
    parse_client_message,
)
from core.server.server import CLOSE_CODE_FORBIDDEN, CLOSE_CODE_UNAUTHORIZED, AGEServer

# ==============================================================================
# 1. Protocol Tests
# ==============================================================================

def test_protocol_parse_valid_auth():
    msg = parse_client_message({"type": "auth", "token": "a" * 32})
    assert isinstance(msg, AuthRequest)
    assert msg.token == "a" * 32


def test_protocol_parse_execute_command():
    msg = parse_client_message({"type": "execute_command", "text": "open notepad", "force_confirmed": False})
    assert isinstance(msg, ExecuteCommandRequest)
    assert msg.text == "open notepad"
    assert msg.force_confirmed is False


from pydantic import ValidationError


def test_protocol_parse_rejects_empty_command():
    with pytest.raises((ValidationError, ValueError)):
        parse_client_message({"type": "execute_command", "text": "   "})



def test_protocol_parse_rejects_unknown_type():
    with pytest.raises(ValueError, match="Unknown or unsupported message type"):
        parse_client_message({"type": "malicious_hack", "payload": "data"})


# ==============================================================================
# 2. Server Security Rule 1 (Loopback Binding)
# ==============================================================================

def test_server_rejects_wildcard_host():
    cfg = AppConfig(server=ServerConfig(host="127.0.0.1"))
    cfg.server.host = "0.0.0.0"
    with pytest.raises(ValueError, match="never 0.0.0.0"):
        AGEServer(config=cfg)


def test_server_rejects_external_host():
    cfg = AppConfig(server=ServerConfig(host="127.0.0.1"))
    cfg.server.host = "192.168.1.50"
    with pytest.raises(ValueError, match="must be loopback"):
        AGEServer(config=cfg)


# ==============================================================================
# 3. Server End-to-End Async Tests
# ==============================================================================

@pytest.fixture
def test_env(tmp_path: Path):
    token_file = tmp_path / "data" / "sessions" / "test.token"
    token_mgr = SessionTokenManager(token_path=token_file, base_dir=tmp_path)
    secret_token = token_mgr.generate_token(32)

    cfg = AppConfig(
        server=ServerConfig(
            host="127.0.0.1",
            port=9876,
            allowed_origins=["http://127.0.0.1:9876", "http://localhost:9876"],
            token_file=str(token_file),
        )
    )

    router = MagicMock(spec=CommandRouter)
    server = AGEServer(config=cfg, router=router, token_mgr=token_mgr)
    return {
        "server": server,
        "token": secret_token,
        "token_mgr": token_mgr,
        "router": router,
        "port": 9876,
    }


@pytest.mark.anyio
async def test_server_auth_success_and_status(test_env):
    server = test_env["server"]
    token = test_env["token"]
    port = test_env["port"]

    await server.start()
    try:
        uri = f"ws://127.0.0.1:{port}"
        async with connect(uri) as ws:
            # 1. Send valid auth message
            auth_payload = json.dumps({"type": "auth", "token": token})
            await ws.send(auth_payload)

            auth_res = json.loads(await ws.recv())
            assert auth_res["type"] == "auth_result"
            assert auth_res["success"] is True

            # 2. Receive initial status update
            status_res = json.loads(await ws.recv())
            assert status_res["type"] == "status_update"
            assert status_res["offline_mode"] is True
            assert status_res["core_running"] is True

            # 3. Query status explicitly
            await ws.send(json.dumps({"type": "get_status"}))
            status_res2 = json.loads(await ws.recv())
            assert status_res2["type"] == "status_update"
    finally:
        await server.stop()


@pytest.mark.anyio
async def test_server_refuses_wrong_token(test_env):
    server = test_env["server"]
    port = test_env["port"]

    await server.start()
    try:
        uri = f"ws://127.0.0.1:{port}"
        async with connect(uri) as ws:
            # Send invalid token
            bad_payload = json.dumps({"type": "auth", "token": "invalid_wrong_token_1234567890"})
            await ws.send(bad_payload)

            auth_res = json.loads(await ws.recv())
            assert auth_res["type"] == "auth_result"
            assert auth_res["success"] is False

            # Connection should be closed by server with code 4401
            with pytest.raises(ConnectionClosed) as exc_info:
                await ws.recv()
            code = exc_info.value.rcvd.code if exc_info.value.rcvd else exc_info.value.code
            assert code == CLOSE_CODE_UNAUTHORIZED
    finally:
        await server.stop()


@pytest.mark.anyio
async def test_server_refuses_unauthorized_origin(test_env):
    server = test_env["server"]
    port = test_env["port"]

    await server.start()
    try:
        uri = f"ws://127.0.0.1:{port}"
        # Connect with external untrusted Origin header
        headers = {"Origin": "http://evil-attacker-site.com"}
        with pytest.raises(ConnectionClosed) as exc_info:
            async with connect(uri, additional_headers=headers) as ws:
                await ws.recv()
        code = exc_info.value.rcvd.code if exc_info.value.rcvd else exc_info.value.code
        assert code == CLOSE_CODE_FORBIDDEN
    finally:
        await server.stop()


@pytest.mark.anyio
async def test_server_emergency_stop_broadcast(test_env):
    server = test_env["server"]
    token = test_env["token"]
    port = test_env["port"]

    await server.start()
    try:
        uri = f"ws://127.0.0.1:{port}"
        async with connect(uri) as ws:
            await ws.send(json.dumps({"type": "auth", "token": token}))
            await ws.recv()  # auth_result
            await ws.recv()  # initial status

            # Trigger emergency stop
            with patch.object(server.emergency_mgr, "trigger") as mock_trigger:
                await ws.send(json.dumps({"type": "emergency_stop"}))
                event = json.loads(await ws.recv())
                assert event["type"] == "emergency_stop_triggered"
                assert "halted" in event["message"]
                mock_trigger.assert_called_once()
    finally:
        await server.stop()


@pytest.mark.anyio
async def test_server_serves_token_api(test_env):
    import asyncio
    import urllib.request

    server = test_env["server"]
    token = test_env["token"]
    port = test_env["port"]

    await server.start()
    try:
        def fetch():
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/token") as r:
                return r.status, json.loads(r.read().decode())

        status_code, body = await asyncio.to_thread(fetch)
        assert status_code == 200
        assert body["token"] == token
    finally:
        await server.stop()


@pytest.mark.anyio
async def test_server_serves_index_html(test_env):
    import asyncio
    import urllib.request

    server = test_env["server"]
    port = test_env["port"]

    await server.start()
    try:
        def fetch():
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as r:
                return r.status, r.read()

        status_code, content = await asyncio.to_thread(fetch)
        assert status_code in (200, 503)
        assert len(content) > 0
    finally:
        await server.stop()


@pytest.mark.anyio
async def test_server_voice_continuous_loop_silence_timeout(test_env):
    server = test_env["server"]
    mock_pipeline = MagicMock()
    mock_pipeline.listen.return_value = ""  # Silence
    server._voice_pipeline = mock_pipeline

    await server._run_voice_cycle(max_silence_cycles=2)
    assert server.current_state == "idle"
    assert mock_pipeline.listen.call_count == 2


@pytest.mark.anyio
async def test_server_voice_continuous_loop_exit_phrase(test_env):
    from core.brain.router import CommandResult
    server = test_env["server"]
    mock_pipeline = MagicMock()
    mock_pipeline.listen.side_effect = ["khuda hafiz"]
    mock_pipeline.speak.return_value = True
    server._voice_pipeline = mock_pipeline

    server.router.execute_command.return_value = CommandResult(
        matched=True,
        success=True,
        message="Khuda Hafiz! Apna khayal rakhiyega.",
        tool_name="chat",
    )

    await server._run_voice_cycle()
    assert server.current_state == "idle"
    assert mock_pipeline.listen.call_count == 1
    mock_pipeline.speak.assert_called_once_with("Khuda Hafiz! Apna khayal rakhiyega.")


@pytest.mark.anyio
async def test_server_stop_listening_message(test_env):
    import asyncio
    server = test_env["server"]
    token = test_env["token"]
    port = test_env["port"]

    await server.start()
    try:
        uri = f"ws://127.0.0.1:{port}"
        async with connect(uri) as ws:
            await ws.send(json.dumps({"type": "auth", "token": token}))
            await ws.recv()  # auth_result
            await ws.recv()  # initial status

            await ws.send(json.dumps({"type": "stop_listening"}))
            await asyncio.sleep(0.1)
            assert server._stop_listening_requested is True
            assert server.current_state == "idle"
    finally:
        await server.stop()


