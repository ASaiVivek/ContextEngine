"""MCP tool surface for the context engine.

Tools return structured models the official MCP client validates against
output schemas. Errors are tool failures. Empty relevance is a successful
response with an explicit status, not an error.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from context_engine.api import ContextEngine
from context_engine.models import (
    ContextBudget,
    ContextEngineStatus,
    ContextLifecycleEvent,
    DomainFilterMode,
    GetRequest,
    GetResponse,
    LifecycleStage,
    RecordLifecycleRequest,
    RecordLifecycleResponse,
    ResolveRequest,
    ResolveResponse,
)


def build_server(engine: ContextEngine | None = None) -> FastMCP:
    """Build an MCP server bound to one engine instance (one ledger)."""
    app = FastMCP("context-engine")
    bound = engine if engine is not None else ContextEngine()

    def require_session(session_id: str) -> str:
        cleaned = session_id.strip()
        if not cleaned:
            raise ToolError("session_id is required and must be non-empty")
        return cleaned

    @app.tool()
    def resolve_context(
        session_id: str,
        task_description: str,
        repository: str | None = None,
        domain: str | None = None,
        domain_filter: str = DomainFilterMode.HINT.value,
        recent_event: str | None = None,
        max_items: int | None = None,
        max_tokens: int | None = None,
        include_content: bool = True,
    ) -> ResolveResponse:
        """Rank knowledge for a task. Empty matches return status no_match or domain_empty."""
        cleaned = require_session(session_id)
        if not task_description.strip():
            raise ToolError("task_description is required and must be non-empty")
        try:
            filter_mode = DomainFilterMode(domain_filter)
        except ValueError as exc:
            raise ToolError(
                "domain_filter must be 'hint' or 'restrict'"
            ) from exc
        if max_items is not None and max_items < 1:
            raise ToolError("max_items must be >= 1 when provided")
        if max_tokens is not None and max_tokens < 1:
            raise ToolError("max_tokens must be >= 1 when provided")

        budget = None
        if max_items is not None or max_tokens is not None:
            budget = ContextBudget(max_items=max_items, max_tokens=max_tokens)

        return bound.resolve(
            ResolveRequest(
                session_id=cleaned,
                task_description=task_description,
                repository=repository,
                domain=domain,
                domain_filter=filter_mode,
                recent_event=recent_event,
                budget=budget,
                include_content=include_content,
            )
        )

    @app.tool()
    def get_context(session_id: str, item_ids: list[str]) -> GetResponse:
        """Return catalog content for item ids. Unknown ids are listed, not invented."""
        cleaned = require_session(session_id)
        if not item_ids:
            raise ToolError("item_ids must contain at least one id")
        if any(not item_id.strip() for item_id in item_ids):
            raise ToolError("item_ids must not contain empty ids")
        return bound.get(GetRequest(session_id=cleaned, item_ids=item_ids))

    @app.tool()
    def get_session_status(session_id: str) -> ContextEngineStatus:
        """Inspect engine ledger for a session. This is not the agent's context window."""
        cleaned = require_session(session_id)
        return bound.get_status(cleaned)

    @app.tool()
    def record_context_usage(
        session_id: str,
        item_id: str,
        version: str,
        detail: str | None = None,
    ) -> RecordLifecycleResponse:
        """Record a host-reported usage signal. Omitted unless the host provides it."""
        cleaned = require_session(session_id)
        if not item_id.strip() or not version.strip():
            raise ToolError("item_id and version are required")
        return bound.record_lifecycle(
            RecordLifecycleRequest(
                events=[
                    ContextLifecycleEvent(
                        session_id=cleaned,
                        item_id=item_id.strip(),
                        version=version.strip(),
                        stage=LifecycleStage.REPORTED_USED,
                        detail=detail,
                    )
                ]
            )
        )

    return app


mcp = build_server()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
