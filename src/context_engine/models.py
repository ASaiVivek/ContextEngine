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
    missing_item_ids: list[str] = Field(
        default_factory=list,
        description="Requested ids that are not in the catalog. Not an agent-context signal.",
    )
    retrieved_at: datetime = Field(default_factory=utc_now)


class LifecycleStage(str, Enum):
    """Stages the engine can observe directly or via host signals."""

    SELECTED = "selected"
    RETURNED = "returned"
    REPORTED_USED = "reported_used"


class LifecycleRecordOutcome(str, Enum):
    RECORDED = "recorded"
    DUPLICATE_SKIPPED = "duplicate_skipped"


class UsageOutcome(str, Enum):
    """Legacy and host-feedback outcomes (not engine lifecycle stages)."""

    DELIVERED = "delivered"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    REJECTED_BUDGET = "rejected_budget"
    AGENT_FEEDBACK_POSITIVE = "agent_feedback_positive"
    AGENT_FEEDBACK_NEGATIVE = "agent_feedback_negative"


class ContextLifecycleEvent(BaseModel):
    session_id: str
    item_id: str
    version: str
    stage: LifecycleStage
    detail: str | None = None
    recorded_at: datetime = Field(default_factory=utc_now)


class RecordLifecycleRequest(BaseModel):
    events: list[ContextLifecycleEvent] = Field(min_length=1)


class LifecycleRecordResult(BaseModel):
    event: ContextLifecycleEvent
    outcome: LifecycleRecordOutcome
    message: str | None = None


class RecordLifecycleResponse(BaseModel):
    session_id: str
    results: list[LifecycleRecordResult] = Field(default_factory=list)


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
    selected_count: int = 0
    returned_count: int = 0
    reported_used_count: int = 0
    duplicate_select_skips: int = 0
    duplicate_return_skips: int = 0
    first_selected_at: datetime | None = None
    last_selected_at: datetime | None = None
    first_returned_at: datetime | None = None
    last_returned_at: datetime | None = None
    first_reported_used_at: datetime | None = None
    last_reported_used_at: datetime | None = None
    superseded: bool = False
    superseded_by_version: str | None = None
    superseded_at: datetime | None = None
    agent_feedback: list[UsageOutcome] = Field(default_factory=list)


class LifecycleTotals(BaseModel):
    selected: int = 0
    returned: int = 0
    reported_used: int = 0
    duplicate_select_skips: int = 0
    duplicate_return_skips: int = 0


class ContextEngineStatus(BaseModel):
    session_id: str
    entries: list[LedgerEntry] = Field(default_factory=list)
    totals: LifecycleTotals = Field(default_factory=LifecycleTotals)
    observation_scope: str = Field(
        default=(
            "Returned counts reflect engine/API delivery only. "
            "Reported-used and feedback require explicit host signals; "
            "the engine does not read the agent context window."
        ),
    )

    @property
    def total_deliveries(self) -> int:
        """Legacy alias for returned item count."""
        return self.totals.returned
