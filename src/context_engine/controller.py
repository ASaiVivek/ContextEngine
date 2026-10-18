"""Orchestration hooks for dynamic delivery (Phase D).

Phase 1 stub: delegates to resolver; future work will react to lifecycle events.
"""

from __future__ import annotations

from pathlib import Path

from context_engine.catalog import KnowledgeCatalog
from context_engine.models import ResolveRequest, ResolveResponse
from context_engine.resolver import resolve_candidates


class ContextController:
    def __init__(self, catalog: KnowledgeCatalog, knowledge_root: Path) -> None:
        self._catalog = catalog
        self._knowledge_root = knowledge_root

    def plan_resolve(self, request: ResolveRequest) -> ResolveResponse:
        result = resolve_candidates(self._catalog, self._knowledge_root, request)
        return ResolveResponse(
            session_id=request.session_id,
            status=result.status,
            message=result.message,
            candidates=result.candidates,
            catalog_version=result.catalog_version,
        )
