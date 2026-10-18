"""MCP tool surface for the context engine.

Phase A/C: expose resolve_context and get_context to compatible clients.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from context_engine.api import ContextEngine
from context_engine.models import GetRequest, ResolveRequest

mcp = FastMCP("context-engine")
_engine: ContextEngine | None = None


def get_engine() -> ContextEngine:
    global _engine
    if _engine is None:
        _engine = ContextEngine()
    return _engine


@mcp.tool()
def resolve_context(
    session_id: str,
    task_description: str,
    repository: str | None = None,
    domain: str | None = None,
    recent_event: str | None = None,
    max_items: int | None = None,
) -> str:
    """Find ranked knowledge candidates for the current task."""
    from context_engine.models import ContextBudget

    engine = get_engine()
    budget = ContextBudget(max_items=max_items) if max_items is not None else None
    response = engine.resolve(
        ResolveRequest(
            session_id=session_id,
            task_description=task_description,
            repository=repository,
            domain=domain,
            recent_event=recent_event,
            budget=budget,
        )
    )
    return json.dumps(response.model_dump(mode="json"), indent=2)


@mcp.tool()
def get_context(session_id: str, item_ids: list[str]) -> str:
    """Retrieve full content for selected knowledge item ids."""
    engine = get_engine()
    response = engine.get(GetRequest(session_id=session_id, item_ids=item_ids))
    return json.dumps(response.model_dump(mode="json"), indent=2)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
