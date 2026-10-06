"""Base interface and return model for all tools.

Security Rule 3:
Tool calls must be validated against strict schemas (Pydantic).
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """Result returned by tool execution."""
    success: bool
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class BaseTool(ABC):
    """Abstract base class for AGE tools."""

    name: str = ""
    description: str = ""
    is_dangerous: bool = False
    args_schema: type[BaseModel] = BaseModel

    def run(self, **kwargs: Any) -> ToolResult:
        """Validate input parameters against strict Pydantic schema and execute tool.

        Args:
            **kwargs: Unvalidated keyword arguments from LLM or Router.

        Returns:
            ToolResult object.
        """
        # Security Rule 3: Strict schema validation before running
        validated_args = self.args_schema.model_validate(kwargs)
        return self.execute(**validated_args.model_dump())

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Perform the tool action with validated parameters."""
