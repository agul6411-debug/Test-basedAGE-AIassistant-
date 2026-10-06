"""Unit tests for tool definitions, schemas, and execution."""

import pytest
from pydantic import ValidationError

from core.tools.registry import registry
from core.tools.set_brightness import SetBrightnessSchema
from core.tools.set_volume import SetVolumeSchema
from core.tools.type_text import TypeTextSchema
from core.tools.web_search import WebSearchSchema


def test_all_tools_registered():
    expected_tools = {
        "open_app",
        "close_app",
        "set_volume",
        "set_brightness",
        "lock_screen",
        "web_search",
        "youtube_search",
        "type_text",
        "shutdown",
        "restart",
        "close_all",
    }
    for tool_name in expected_tools:
        assert tool_name in registry
        tool = registry.get(tool_name)
        assert tool is not None
        assert tool.name == tool_name
        assert len(tool.description) > 0


def test_dangerous_flags():
    # Only dangerous tools must have is_dangerous == True
    dangerous_tools = {"shutdown", "restart", "close_all"}
    for tool in registry.list_tools():
        if tool.name in dangerous_tools:
            assert tool.is_dangerous is True
        else:
            assert tool.is_dangerous is False


def test_set_volume_schema():
    valid = SetVolumeSchema(level=50)
    assert valid.level == 50

    with pytest.raises(ValidationError):
        SetVolumeSchema(level=150)  # > 100

    with pytest.raises(ValidationError):
        SetVolumeSchema(level=-10)  # < 0


def test_set_brightness_schema():
    valid = SetBrightnessSchema(level=80)
    assert valid.level == 80

    with pytest.raises(ValidationError):
        SetBrightnessSchema(level=120)


def test_web_search_schema_and_execution(monkeypatch):
    schema = WebSearchSchema(query="fastapi python")
    assert schema.query == "fastapi python"

    tool = registry.get("web_search")
    assert tool is not None

    # Mock webbrowser.open_new_tab to verify URL encoding without opening real browser
    opened_urls = []
    monkeypatch.setattr("webbrowser.open_new_tab", lambda url: opened_urls.append(url))

    result = tool.run(query="python & c++ tutorial")
    assert result.success is True
    assert len(opened_urls) == 1
    assert "python+%26+c%2B%2B+tutorial" in opened_urls[0]


def test_youtube_search_execution(monkeypatch):
    tool = registry.get("youtube_search")
    assert tool is not None

    opened_urls = []
    monkeypatch.setattr("webbrowser.open_new_tab", lambda url: opened_urls.append(url))

    result = tool.run(query="cooking pasta")
    assert result.success is True
    assert len(opened_urls) == 1
    assert "cooking+pasta" in opened_urls[0]


def test_type_text_schema():
    valid = TypeTextSchema(text="Hello world")
    assert valid.text == "Hello world"

    with pytest.raises(ValidationError):
        TypeTextSchema(text="")  # Empty rejected
