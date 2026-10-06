"""Tool to perform a web search in the default browser."""

import urllib.parse
import webbrowser
from typing import Any

from pydantic import BaseModel, Field

from core.tools.base import BaseTool, ToolResult
from core.tools.registry import registry


class WebSearchSchema(BaseModel):
    """Schema for web search."""
    query: str = Field(..., min_length=1, max_length=500, description="Search query string")


class WebSearchTool(BaseTool):
    """Performs a web search via the default desktop web browser."""

    name = "web_search"
    description = "Open default browser with a Google search for query."
    is_dangerous = False
    args_schema = WebSearchSchema

    def execute(self, query: str, **kwargs: Any) -> ToolResult:
        clean_query = query.strip()
        if not clean_query:
            return ToolResult(success=False, message="Search query cannot be empty.")

        encoded_query = urllib.parse.quote_plus(clean_query)
        url = f"https://www.google.com/search?q={encoded_query}"

        try:
            webbrowser.open_new_tab(url)
            return ToolResult(
                success=True,
                message=f"Opened search for '{clean_query}'.",
                data={"query": clean_query, "url": url},
            )
        except Exception as e:  # noqa: BLE001
            return ToolResult(success=False, message=f"Failed to open browser: {e}")


registry.register(WebSearchTool())
