"""Tests for CommandRouter routing, example phrases, and security attack cases."""

import pytest

from core.brain.router import CommandRouter


@pytest.fixture
def router():
    return CommandRouter()


def test_route_open_notepad(router: CommandRouter):
    intent = router.route_intent("open notepad")
    assert intent == ("open_app", {"app_name": "notepad"})


def test_route_volume_up(router: CommandRouter):
    intent = router.route_intent("volume up")
    assert intent == ("set_volume", {"delta": 10})


def test_route_set_volume_to_40(router: CommandRouter):
    intent = router.route_intent("set volume to 40")
    assert intent == ("set_volume", {"level": 40})


def test_route_search_youtube(router: CommandRouter):
    intent = router.route_intent("search youtube for cooking videos")
    assert intent == ("youtube_search", {"query": "cooking videos"})


def test_route_lock_screen(router: CommandRouter):
    intent = router.route_intent("lock the screen")
    assert intent == ("lock_screen", {})


def test_route_close_notepad(router: CommandRouter):
    intent = router.route_intent("close notepad")
    assert intent == ("close_app", {"app_name": "notepad"})


def test_route_web_search(router: CommandRouter):
    intent = router.route_intent("search web for python 3.11")
    assert intent == ("web_search", {"query": "python 3.11"})


def test_route_dangerous_tools(router: CommandRouter):
    assert router.route_intent("shutdown")[0] == "shutdown"
    assert router.route_intent("restart")[0] == "restart"
    assert router.route_intent("close all")[0] == "close_all"
    assert router.route_intent("restore my desktop")[0] == "restore_layout"


def test_route_layout_commands(router: CommandRouter):
    assert router.route_intent("save my desktop") == ("save_layout", {})
    assert router.route_intent("save desktop") == ("save_layout", {})
    assert router.route_intent("save layout") == ("save_layout", {})
    assert router.route_intent("backup layout") == ("save_layout", {})
    assert router.route_intent("restore my desktop") == ("restore_layout", {})
    assert router.route_intent("restore desktop") == ("restore_layout", {})
    assert router.route_intent("restore layout") == ("restore_layout", {})



# ==============================================================================
# Security Attack Cases
# ==============================================================================

def test_attack_unknown_app_name(router: CommandRouter):
    result = router.execute_command("open evil_backdoor")
    assert result.matched is True
    assert result.success is False
    assert "not permitted" in result.message.lower()


def test_attack_command_injection_ampersand(router: CommandRouter):
    # Command injection strings containing shell metacharacters must be rejected
    intent = router.route_intent("open notepad & del *")
    assert intent is None


def test_attack_command_injection_semicolon(router: CommandRouter):
    intent = router.route_intent("open notepad; format c:")
    assert intent is None


def test_attack_command_injection_pipe(router: CommandRouter):
    intent = router.route_intent("open notepad | calc")
    assert intent is None


def test_attack_very_long_input(router: CommandRouter):
    huge_input = "open notepad " + ("A" * 15000)
    result = router.execute_command(huge_input)
    assert isinstance(result.matched, bool)
    assert not result.success


def test_attack_empty_input(router: CommandRouter):
    result = router.execute_command("")
    assert result.matched is False
    assert result.message == "Input is empty."


def test_attack_whitespace_only(router: CommandRouter):
    result = router.execute_command("    \t\n  ")
    assert result.matched is False
    assert result.message == "Input is empty."
