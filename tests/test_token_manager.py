"""Tests for secure session token generation and verification."""

from pathlib import Path

import pytest

from core.safety.token_manager import SessionTokenManager, TokenError


def test_generate_and_read_token(tmp_path: Path):
    token_file = tmp_path / "session.token"
    manager = SessionTokenManager(token_path=token_file, base_dir=tmp_path)

    token = manager.generate_token()
    assert len(token) >= 32
    assert token_file.exists()

    read_back = manager.read_token()
    assert read_back == token


def test_read_token_missing_file(tmp_path: Path):
    token_file = tmp_path / "nonexistent.token"
    manager = SessionTokenManager(token_path=token_file, base_dir=tmp_path)

    with pytest.raises(TokenError):
        manager.read_token()


def test_verify_token():
    t1 = "super-secret-token-1234567890"
    t2 = "super-secret-token-1234567890"
    t3 = "wrong-token-9876543210"

    assert SessionTokenManager.verify_token(t1, t2) is True
    assert SessionTokenManager.verify_token(t1, t3) is False
    assert SessionTokenManager.verify_token("", t1) is False
    assert SessionTokenManager.verify_token(t1, "") is False
