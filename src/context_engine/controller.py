"""Orchestration hooks for dynamic delivery (Phase D).

Phase 1 stub: delegates to resolver; future work will react to lifecycle events.
"""

from __future__ import annotations

from context_engine.catalog import KnowledgeCatalog
from context_engine.models import ResolveRequest, ResolveResponse
from context_engine.resolver import resolve_candidates


class ContextController:
    def __init__(self, catalog: KnowledgeCatalog) -> None:
        self._catalog = catalog

    def plan_resolve(self, request: ResolveRequest) -> ResolveResponse:
        candidates = resolve_candidates(self._catalog, request)
        return ResolveResponse(session_id=request.session_id, candidates=candidates)
