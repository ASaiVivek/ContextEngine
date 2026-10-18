"""Relevance ranking for knowledge candidates (keyword baseline for Phase B)."""

from __future__ import annotations

import re

from context_engine.catalog import CatalogItemRef, KnowledgeCatalog
from context_engine.models import ContextBudget, RankedCandidate, ResolveRequest

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


def _score_item(
    item: CatalogItemRef,
    query_tokens: set[str],
    domain_hint: str | None,
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0

    item_text = " ".join(
        filter(
            None,
            [item.id, item.domain or "", item.summary or "", " ".join(item.tags)],
        )
    )
    item_tokens = _tokens(item_text)
    overlap = query_tokens & item_tokens
    if overlap:
        overlap_score = min(1.0, len(overlap) / max(3, len(query_tokens)))
        score += 0.5 * overlap_score
        reasons.append(f"keyword overlap: {', '.join(sorted(overlap)[:5])}")

    if domain_hint and item.domain and domain_hint.lower() == item.domain.lower():
        score += 0.35
        reasons.append(f"domain match: {item.domain}")

    if item.id.replace("/", " ") and any(t in item.id for t in query_tokens):
        score += 0.15
        reasons.append("id matches query terms")

    return min(1.0, score), reasons


def resolve_candidates(
    catalog: KnowledgeCatalog,
    request: ResolveRequest,
) -> list[RankedCandidate]:
    parts = [request.task_description]
    if request.recent_event:
        parts.append(request.recent_event)
    if request.repository:
        parts.append(request.repository)
    query_tokens = _tokens(" ".join(parts))

    ranked: list[RankedCandidate] = []
    for item in catalog.items:
        score, reasons = _score_item(item, query_tokens, request.domain)
        if score <= 0:
            continue
        ranked.append(
            RankedCandidate(
                item_id=item.id,
                version=item.version,
                score=round(score, 4),
                reasons=reasons,
                summary=item.summary,
            )
        )

    ranked.sort(key=lambda c: c.score, reverse=True)
    return _apply_budget(ranked, request.budget)


def _apply_budget(
    candidates: list[RankedCandidate],
    budget: ContextBudget | None,
) -> list[RankedCandidate]:
    if not budget or budget.max_items is None:
        return candidates
    return candidates[: budget.max_items]
