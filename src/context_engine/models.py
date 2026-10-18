"""Core request/response models for the context engine API.

These types are independent of MCP or any specific agent runtime.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DomainFilterMode(str, Enum):
    """How the optional domain hint affects candidate selection."""

    HINT = "hint"
    RESTRICT = "restrict"


class ResolveStatus(str, Enum):
    """Outcome when no candidates qualify, or when results are returned."""

    MATCHED = "matched"
    NO_MATCH = "no_match"
    DOMAIN_EMPTY = "domain_empty"


class ContextBudget(BaseModel):
    """Optional limits the adapter can pass so the engine can trim results."""

    max_items: int | None = Field(
        default=None,
        description="Maximum number of knowledge items to return.",
    )
    max_tokens: int | None = Field(
        default=None,
        description="Approximate token budget for returned content (adapter-defined).",
    )


class ResolveRequest(BaseModel):
    """Find relevant knowledge candidates for the current task."""

    session_id: str = Field(description="Stable id for this agent session or run.")
    task_description: str = Field(
        description="What the agent is trying to accomplish or the current user goal.",
    )
    repository: str | None = Field(
        default=None,
        description="Repository name, path, or domain scope when available.",
    )
    domain: str | None = Field(
        default=None,
        description="Business or technical domain hint (e.g. payments, infrastructure).",
    )
    domain_filter: DomainFilterMode = Field(
        default=DomainFilterMode.HINT,
        description="hint: boost domain matches; restrict: only items in that domain.",
    )
    include_content: bool = Field(
        default=True,
        description="When true, resolve loads and returns markdown content per candidate.",
    )
    recent_event: str | None = Field(
        default=None,
        description="Latest discovery, error, or tool result that may change relevance.",
    )
    budget: ContextBudget | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RankedCandidate(BaseModel):
    """A catalog item ranked for potential delivery."""

    item_id: str = Field(description="Stable source id from the knowledge catalog.")
    version: str
    score: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(
        default_factory=list,
        description="Human-readable, deterministic relevance explanations.",
    )
    summary: str | None = None
    content: str | None = Field(
        default=None,
        description="Full markdown body when include_content is true and the file exists.",
    )


class ResolveResponse(BaseModel):
    session_id: str
    status: ResolveStatus = ResolveStatus.MATCHED
    message: str | None = Field(
        default=None,
        description="Set when status is not matched (e.g. no relevant knowledge).",
    )
    candidates: list[RankedCandidate] = Field(default_factory=list)
    catalog_version: str | None = None
    resolved_at: datetime = Field(default_factory=utc_now)


class GetRequest(BaseModel):
    """Retrieve full content for selected catalog items."""

    session_id: str
    item_ids: list[str] = Field(min_length=1)
    include_content: bool = True


class KnowledgeItem(BaseModel):
    item_id: str
    version: str
    domain: str | None = None
    tags: list[str] = Field(default_factory=list)
    summary: str | None = None
    content: str | None = None
    content_path: str | None = None


class GetResponse(BaseModel):
    session_id: str
    items: list[KnowledgeItem]
    retrieved_at: datetime = Field(default_factory=utc_now)


class UsageOutcome(str, Enum):
    DELIVERED = "delivered"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    REJECTED_BUDGET = "rejected_budget"
    AGENT_FEEDBACK_POSITIVE = "agent_feedback_positive"
    AGENT_FEEDBACK_NEGATIVE = "agent_feedback_negative"


class UsageEvent(BaseModel):
    session_id: str
    item_id: str
    version: str
    outcome: UsageOutcome
    detail: str | None = None
    recorded_at: datetime = Field(default_factory=utc_now)


class RecordUsageRequest(BaseModel):
    events: list[UsageEvent] = Field(min_length=1)


class LedgerEntry(BaseModel):
    item_id: str
    version: str
    first_delivered_at: datetime
    last_delivered_at: datetime
    delivery_count: int = 1
    outcomes: list[UsageOutcome] = Field(default_factory=list)


class ContextEngineStatus(BaseModel):
    session_id: str
    entries: list[LedgerEntry] = Field(default_factory=list)
    total_deliveries: int = 0
