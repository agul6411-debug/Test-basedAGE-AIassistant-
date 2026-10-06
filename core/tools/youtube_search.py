"""Tool to perform a YouTube search in the default browser."""

import urllib.parse
import webbrowser
from typing import Any

from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolResult
from core.tools.registry import registry


class YouTubeSearchSchema(BaseModel):
    """Schema for YouTube search."""
    query: str = Field(..., min_length=1, max_length=500, description="Video search query string")


class YouTubeSearchTool(BaseTool):
    """Opens YouTube search results in default browser."""

    name = "youtube_search"
    description = "Search YouTube for videos matching the query."
    is_dangerous = False
    args_schema = YouTubeSearchSchema

    def execute(self, query: str, **kwargs: Any) -> ToolResult:
        clean_query = query.strip()
        if not clean_query:
            return ToolResult(success=False, message="YouTube query cannot be empty.")

        encoded_query = urllib.parse.quote_plus(clean_query)
        url = f"https://www.youtube.com/results?search_query={encoded_query}"

        try:
            webbrowser.open_new_tab(url)
            return ToolResult(
                success=True,
                message=f"Opened YouTube search for '{clean_query}'.",
                data={"query": clean_query, "url": url},
            )
        except Exception as e:  # noqa: BLE001
            return ToolResult(success=False, message=f"Failed to open browser: {e}")


registry.register(YouTubeSearchTool())
