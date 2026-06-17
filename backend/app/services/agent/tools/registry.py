"""Tool allowlist + Pydantic IO schema binding. Rejects non-allowlisted names before execution (FR-007/008)."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from pydantic import BaseModel

from app.core.exceptions import RaseedError

# Type alias: an async tool function that takes validated args and returns a dict
ToolFn = Callable[..., Coroutine[Any, Any, dict[str, Any]]]


class ToolSpec:
    __slots__ = ("name", "input_schema", "fn")

    def __init__(self, name: str, input_schema: type[BaseModel], fn: ToolFn) -> None:
        self.name = name
        self.input_schema = input_schema
        self.fn = fn


_registry: dict[str, ToolSpec] = {}


def register_tool(name: str, input_schema: type[BaseModel], fn: ToolFn) -> None:
    _registry[name] = ToolSpec(name=name, input_schema=input_schema, fn=fn)


def get_tool_names() -> list[str]:
    return list(_registry.keys())


async def dispatch(tool_name: str, raw_args: dict[str, Any]) -> dict[str, Any]:
    """Validate args against the Pydantic schema and call the tool; return structured error on failure."""
    if tool_name not in _registry:
        return {"error": f"Unknown tool '{tool_name}'. Allowed tools: {', '.join(_registry)}"}

    spec = _registry[tool_name]
    # Private context fields (injected by the loop, not from LLM) bypass Pydantic validation
    context = {k: v for k, v in raw_args.items() if k.startswith("_")}
    public_args = {k: v for k, v in raw_args.items() if not k.startswith("_")}

    try:
        validated = spec.input_schema.model_validate(public_args)
    except Exception as exc:
        return {"error": f"Invalid arguments for '{tool_name}': {exc}"}

    try:
        return await spec.fn(**validated.model_dump(), **context)
    except RaseedError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        # Never expose a stack trace (FR-010, Art. I)
        return {"error": f"Tool '{tool_name}' failed: {exc!s}"}
