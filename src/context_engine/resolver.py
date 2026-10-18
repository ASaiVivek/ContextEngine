"""Relevance ranking for knowledge candidates (deterministic keyword baseline)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from context_engine.catalog import CatalogItemRef, KnowledgeCatalog, read_item_content
from context_engine.models import (
    ContextBudget,
    DomainFilterMode,
    RankedCandidate,
    ResolveRequest,
    ResolveStatus,
)
from context_engine.tokens import candidate_payload_tokens

_TOKEN = re.compile(r"[a-z0-9]+")

# Fixed weights — documented for explainability and stable ranking.
_WEIGHT_KEYWORD = 0.5
_WEIGHT_DOMAIN = 0.35
_WEIGHT_ID = 0.15


@dataclass(frozen=True)
class ScoreBreakdown:
    keyword: float
    domain: float
    id_path: float
    keyword_terms: tuple[str, ...] = ()

    @property
    def total(self) -> float:
        return min(1.0, round(self.keyword + self.domain + self.id_path, 4))

    def to_reasons(self) -> list[str]:
        reasons: list[str] = []
        if self.keyword > 0:
            terms = ", ".join(self.keyword_terms) if self.keyword_terms else "none"
            reasons.append(f"keyword_overlap:+{self.keyword:.4f} (terms: {terms})")
        if self.domain > 0:
            reasons.append(f"domain_match:+{self.domain:.4f}")
        if self.id_path > 0:
            reasons.append(f"id_path_match:+{self.id_path:.4f}")
        reasons.append(f"score_total:{self.total:.4f}")
        return reasons


@dataclass(frozen=True)
class ResolveResult:
    candidates: list[RankedCandidate]
    status: ResolveStatus
    message: str | None
    catalog_version: str


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


def _score_item(
    item: CatalogItemRef,
    query_tokens: set[str],
    domain_hint: str | None,
    content_text: str | None,
) -> ScoreBreakdown:
    searchable = " ".join(
        filter(
            None,
            [
                item.id,
                item.domain or "",
                item.summary or "",
                " ".join(item.tags),
                content_text or "",
            ],
        )
    )
    item_tokens = _tokens(searchable)
    overlap = sorted(query_tokens & item_tokens)

    keyword = 0.0
    if overlap and query_tokens:
        keyword = _WEIGHT_KEYWORD * min(1.0, len(overlap) / max(3, len(query_tokens)))
        keyword = round(keyword, 4)

    domain = 0.0
    if domain_hint and item.domain and domain_hint.lower() == item.domain.lower():
        domain = _WEIGHT_DOMAIN

    id_path = 0.0
    id_parts = set(_tokens(item.id.replace("/", " ")))
    if query_tokens & id_parts:
        id_path = _WEIGHT_ID

    return ScoreBreakdown(
        keyword=keyword,
        domain=domain,
        id_path=id_path,
        keyword_terms=tuple(overlap[:10]),
    )


def _load_content(
    knowledge_root: Path,
    item: CatalogItemRef,
    include_content: bool,
) -> tuple[str | None, list[str]]:
    extra_reasons: list[str] = []
    if not include_content:
        return None, extra_reasons
    try:
        return read_item_content(knowledge_root, item), extra_reasons
    except FileNotFoundError:
        extra_reasons.append("content_unavailable:file_missing")
        return None, extra_reasons


def _eligible_items(
    catalog: KnowledgeCatalog,
    request: ResolveRequest,
) -> list[CatalogItemRef]:
    items = list(catalog.items)
    if request.domain and request.domain_filter == DomainFilterMode.RESTRICT:
        domain = request.domain.lower()
        items = [
            item
            for item in items
            if item.domain is not None and item.domain.lower() == domain
        ]
    return items


def resolve_candidates(
    catalog: KnowledgeCatalog,
    knowledge_root: Path,
    request: ResolveRequest,
) -> ResolveResult:
    eligible = _eligible_items(catalog, request)
    if (
        request.domain
        and request.domain_filter == DomainFilterMode.RESTRICT
        and not eligible
    ):
        return ResolveResult(
            candidates=[],
            status=ResolveStatus.DOMAIN_EMPTY,
            message=(
                f"No catalog items in domain '{request.domain}' "
                f"(domain_filter=restrict)."
            ),
            catalog_version=catalog.version,
        )

    parts = [request.task_description]
    if request.recent_event:
        parts.append(request.recent_event)
    if request.repository:
        parts.append(request.repository)
    query_tokens = _tokens(" ".join(parts))

    ranked: list[RankedCandidate] = []
    for item in eligible:
        content, content_reasons = _load_content(
            knowledge_root, item, request.include_content
        )
        breakdown = _score_item(item, query_tokens, request.domain, content)
        if breakdown.total <= 0:
            continue
        reasons = breakdown.to_reasons() + content_reasons
        ranked.append(
            RankedCandidate(
                item_id=item.id,
                version=item.version,
                score=breakdown.total,
                reasons=reasons,
                summary=item.summary,
                content=content,
            )
        )

    ranked.sort(key=lambda c: (-c.score, c.item_id))

    if not ranked:
        if not query_tokens:
            message = "No query terms to match; refine task_description or recent_event."
        else:
            message = "No knowledge items met the relevance threshold for this query."
        return ResolveResult(
            candidates=[],
            status=ResolveStatus.NO_MATCH,
            message=message,
            catalog_version=catalog.version,
        )

    trimmed = _apply_budget(ranked, request.budget)
    message = None
    if ranked and not trimmed and request.budget is not None:
        if request.budget.max_items is not None or request.budget.max_tokens is not None:
            message = (
                "Relevant items were found but none fit within the requested context budget."
            )
    return ResolveResult(
        candidates=trimmed,
        status=ResolveStatus.MATCHED,
        message=message,
        catalog_version=catalog.version,
    )


def _apply_budget(
    candidates: list[RankedCandidate],
    budget: ContextBudget | None,
) -> list[RankedCandidate]:
    if budget is None:
        return candidates

    selected: list[RankedCandidate] = []
    tokens_used = 0

    for candidate in candidates:
        if budget.max_items is not None and len(selected) >= budget.max_items:
            break

        row_tokens = candidate_payload_tokens(
            candidate.item_id,
            candidate.version,
            candidate.reasons,
            candidate.summary,
            candidate.content,
        )

        if budget.max_tokens is not None:
            if selected and tokens_used + row_tokens > budget.max_tokens:
                continue
            if not selected and row_tokens > budget.max_tokens:
                continue
            if tokens_used + row_tokens > budget.max_tokens:
                continue

        selected.append(candidate)
        tokens_used += row_tokens

    return selected
