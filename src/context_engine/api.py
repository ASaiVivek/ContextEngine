"""Public engine API consumed by adapters (MCP, runtime hooks, tests)."""

from __future__ import annotations

from pathlib import Path

from context_engine.catalog import (
    default_knowledge_root,
    load_catalog,
    read_item_content,
)
from context_engine.controller import ContextController
from context_engine.ledger import ContextLedger
from context_engine.models import (
    ContextEngineStatus,
    GetRequest,
    GetResponse,
    KnowledgeItem,
    RecordUsageRequest,
    ResolveRequest,
    ResolveResponse,
)


class ContextEngine:
    """Agent-agnostic context engine."""

    def __init__(
        self,
        knowledge_root: Path | None = None,
        ledger: ContextLedger | None = None,
    ) -> None:
        self._knowledge_root = knowledge_root or default_knowledge_root()
        self._catalog = load_catalog(self._knowledge_root)
        self._ledger = ledger or ContextLedger()
        self._controller = ContextController(self._catalog, self._knowledge_root)

    @property
    def knowledge_root(self) -> Path:
        return self._knowledge_root

    def resolve(self, request: ResolveRequest) -> ResolveResponse:
        """Find relevant knowledge candidates."""
        return self._controller.plan_resolve(request)

    def get(self, request: GetRequest) -> GetResponse:
        """Retrieve selected knowledge items."""
        items: list[KnowledgeItem] = []
        for item_id in request.item_ids:
            ref = self._catalog.get(item_id)
            if ref is None:
                continue
            content = None
            if request.include_content:
                content = read_item_content(self._knowledge_root, ref)
            items.append(
                KnowledgeItem(
                    item_id=ref.id,
                    version=ref.version,
                    domain=ref.domain,
                    tags=ref.tags,
                    summary=ref.summary,
                    content=content,
                    content_path=str(self._knowledge_root / ref.path),
                )
            )
        return GetResponse(session_id=request.session_id, items=items)

    def record_usage(self, request: RecordUsageRequest) -> None:
        """Record delivery and optional usage feedback."""
        for event in request.events:
            self._ledger.record(event)

    def get_status(self, session_id: str) -> ContextEngineStatus:
        """Inspect the context ledger for a session."""
        return self._ledger.status(session_id)

    def filter_undelivered(
        self,
        session_id: str,
        candidates: list,
    ) -> list:
        """Helper for adapters: drop items already delivered in this session."""
        from context_engine.models import RankedCandidate

        result: list[RankedCandidate] = []
        for candidate in candidates:
            if not isinstance(candidate, RankedCandidate):
                raise TypeError("candidates must be RankedCandidate instances")
            if self._ledger.was_delivered(session_id, candidate.item_id, candidate.version):
                continue
            result.append(candidate)
        return result
