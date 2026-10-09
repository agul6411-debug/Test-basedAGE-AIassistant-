"""Tests for CommandRouter routing, example phrases, and security attack cases."""

import pytest

from core.brain.router import CommandRouter


@pytest.fixture
def router():
    r = CommandRouter()
    r.groq_client = None
    return r


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


def test_speech_punctuation_handling(router: CommandRouter):
    assert router.route_intent("open notepad.") == ("open_app", {"app_name": "notepad"})
    assert router.route_intent("volume up!") == ("set_volume", {"delta": 10})
    assert router.route_intent("lock screen?") == ("lock_screen", {})


def test_wake_prefix_stripping(router: CommandRouter):
    assert router.route_intent("hey age, open notepad") == ("open_app", {"app_name": "notepad"})
    assert router.route_intent("my age, open notepad.") == ("open_app", {"app_name": "notepad"})
    assert router.route_intent("please open notepad") == ("open_app", {"app_name": "notepad"})
    assert router.route_intent("open notepad please") == ("open_app", {"app_name": "notepad"})


def test_application_aliases(router: CommandRouter):
    assert router.route_intent("open calculator") == ("open_app", {"app_name": "calc"})
    assert router.route_intent("open vs code") == ("open_app", {"app_name": "vscode"})
    assert router.route_intent("open browser") == ("open_app", {"app_name": "chrome"})
    assert router.route_intent("close calculator") == ("close_app", {"app_name": "calc"})
    assert router.route_intent("open youtube") == ("web_search", {"query": "youtube"})



def test_offline_conversational_queries(router: CommandRouter):
    # Greetings
    res_greet = router.execute_command("hey age")
    assert res_greet.matched is True and res_greet.success is True
    assert "hello" in res_greet.message.lower()

    res_my_age = router.execute_command("my age.")
    assert res_my_age.matched is True and res_my_age.success is True

    # Time & Date
    res_time = router.execute_command("what is the time")
    assert res_time.matched is True and res_time.success is True
    assert "current time" in res_time.message.lower()

    res_date = router.execute_command("what is the date")
    assert res_date.matched is True and res_date.success is True
    assert "today is" in res_date.message.lower()

    # Identity & Help
    res_who = router.execute_command("who are you")
    assert res_who.matched is True and res_who.success is True
    assert "age" in res_who.message.lower()

    res_help = router.execute_command("what can you do")
    assert res_help.matched is True and res_help.success is True

    # Casual conversation
    res_how = router.execute_command("how are you")
    assert res_how.matched is True and res_how.success is True
    assert "great" in res_how.message.lower()

    res_thanks = router.execute_command("thank you")
    assert res_thanks.matched is True and res_thanks.success is True
    assert "welcome" in res_thanks.message.lower()

    res_bye = router.execute_command("goodbye")
    assert res_bye.matched is True and res_bye.success is True
    assert "goodbye" in res_bye.message.lower()


def test_folder_and_file_routing(router: CommandRouter):
    assert router.route_intent("open downloads") == ("open_app", {"app_name": "downloads"})
    assert router.route_intent("open documents") == ("open_app", {"app_name": "documents"})
    assert router.route_intent("open desktop") == ("open_app", {"app_name": "desktop"})
    assert router.route_intent("open word") == ("open_app", {"app_name": "word"})
    assert router.route_intent("open excel") == ("open_app", {"app_name": "excel"})
    assert router.route_intent("open paint") == ("open_app", {"app_name": "paint"})
    assert router.route_intent("open file report.docx") == ("open_app", {"app_name": "report.docx"})


def test_roman_urdu_routing(router: CommandRouter):
    # App & folder opening
    assert router.route_intent("chrome kholo") == ("open_app", {"app_name": "chrome"})
    assert router.route_intent("word khol do") == ("open_app", {"app_name": "word"})
    assert router.route_intent("downloads open karo") == ("open_app", {"app_name": "downloads"})
    assert router.route_intent("excel chalao") == ("open_app", {"app_name": "excel"})

    # App closing
    assert router.route_intent("chrome band karo") == ("close_app", {"app_name": "chrome"})
    assert router.route_intent("word close kardo") == ("close_app", {"app_name": "word"})
    assert router.route_intent("sab band karo") == ("close_all", {})

    # Volume & brightness
    assert router.route_intent("awaz barhao") == ("set_volume", {"delta": 10})
    assert router.route_intent("awaz kam karo") == ("set_volume", {"delta": -10})
    assert router.route_intent("roshni barhao") == ("set_brightness", {"delta": 10})
    assert router.route_intent("brightness kam karo") == ("set_brightness", {"delta": -10})

    # Screen lock & YouTube
    assert router.route_intent("screen lock karo") == ("lock_screen", {})
    assert router.route_intent("youtube par naat chalao") == ("youtube_search", {"query": "naat"})
    assert router.route_intent("suno age chrome kholo") == ("open_app", {"app_name": "chrome"})


def test_roman_urdu_conversational(router: CommandRouter):
    res_how = router.execute_command("kya haal hai")
    assert res_how.matched is True and res_how.success is True
    assert "theek" in res_how.message.lower()

    res_who = router.execute_command("tum kon ho")
    assert res_who.matched is True and res_who.success is True
    assert "age" in res_who.message.lower()

    res_can = router.execute_command("tum kya kar sakte ho")
    assert res_can.matched is True and res_can.success is True

    res_time = router.execute_command("time kya hua hai")
    assert res_time.matched is True and res_time.success is True

    res_date = router.execute_command("aaj kya date hai")
    assert res_date.matched is True and res_date.success is True

    res_thanks = router.execute_command("shukriya")
    assert res_thanks.matched is True and res_thanks.success is True

    res_bye = router.execute_command("allah hafiz")
    assert res_bye.matched is True and res_bye.success is True


def test_stop_commands(router: CommandRouter):
    assert router.route_intent("okey stop") == ("stop", {})
    assert router.route_intent("okay stop") == ("stop", {})
    assert router.route_intent("ok stop") == ("stop", {})
    assert router.route_intent("stop") == ("stop", {})
    assert router.route_intent("ruko") == ("stop", {})
    assert router.route_intent("ruk jao") == ("stop", {})
    assert router.route_intent("chup") == ("stop", {})
    assert router.route_intent("chup karo") == ("stop", {})
    assert router.route_intent("bas karo") == ("stop", {})

    res = router.execute_command("okey stop")
    assert res.matched is True and res.success is True
    assert res.tool_name == "stop"
    assert res.message == "Stopped."


def test_ambiguous_and_pronouns(router: CommandRouter):
    res_open_it = router.execute_command("open it")
    assert res_open_it.matched is True and res_open_it.success is True
    assert "konsi application" in res_open_it.message.lower()

    res_open_this = router.execute_command("open this")
    assert res_open_this.matched is True and res_open_this.success is True
    assert "konsi application" in res_open_this.message.lower()

    res_close_it = router.execute_command("close it")
    assert res_close_it.matched is True and res_close_it.success is True
    assert "konsi application" in res_close_it.message.lower()

    res_ur_open = router.execute_command("isay kholo")
    assert res_ur_open.matched is True and res_ur_open.success is True
    assert "konsi application" in res_ur_open.message.lower()


def test_jokes_and_stories(router: CommandRouter):
    res_joke1 = router.execute_command("tell me a joke")
    assert res_joke1.matched is True and res_joke1.success is True
    assert len(res_joke1.message) > 10

    res_joke2 = router.execute_command("koi joke sunao")
    assert res_joke2.matched is True and res_joke2.success is True
    assert len(res_joke2.message) > 10

    res_story1 = router.execute_command("tell me a story")
    assert res_story1.matched is True and res_story1.success is True
    assert len(res_story1.message) > 20

    res_story2 = router.execute_command("kahani sunao")
    assert res_story2.matched is True and res_story2.success is True
    assert len(res_story2.message) > 20



def test_age_and_feelings(router: CommandRouter):
    res_my_age = router.execute_command("meri age kya hai")
    assert res_my_age.matched is True and res_my_age.success is True
    assert "owner" in res_my_age.message.lower() or "dost" in res_my_age.message.lower()

    res_your_age = router.execute_command("how old are you")
    assert res_your_age.matched is True and res_your_age.success is True
    assert "ai desktop assistant" in res_your_age.message.lower()

    res_tired = router.execute_command("thakan ho rahi hai")
    assert res_tired.matched is True and res_tired.success is True
    assert "aaram" in res_tired.message.lower()

    res_bored = router.execute_command("bor ho rahi hoon")
    assert res_bored.matched is True and res_bored.success is True
    assert "mood" in res_bored.message.lower()

    res_talk = router.execute_command("mujhse baat karo")
    assert res_talk.matched is True and res_talk.success is True
    assert "zaroor" in res_talk.message.lower()

    res_good = router.execute_command("you are good")
    assert res_good.matched is True and res_good.success is True
    assert "shukriya" in res_good.message.lower()


def test_groq_routing(router: CommandRouter):
    from unittest.mock import MagicMock
    from core.brain.groq_client import GroqClient

    mock_groq = MagicMock(spec=GroqClient)
    mock_groq.is_configured = True
    mock_groq.model = "llama-3.3-70b-versatile"
    mock_groq.chat.return_value = "Biryani banane ke liye pehle chawal ubaalein aur gosht ka korma banayein."

    router_with_groq = CommandRouter(groq_client=mock_groq)
    res = router_with_groq.execute_command("mujhe biryani ki recipe batao")

    assert res.matched is True
    assert res.success is True
    assert res.tool_name == "groq_chat"
    assert "biryani" in res.message.lower()
    mock_groq.chat.assert_called_once_with("mujhe biryani ki recipe batao")





