"""Session ledger: engine-observed context lifecycle (not agent context window)."""

from __future__ import annotations

from context_engine.models import (
    ContextEngineStatus,
    ContextLifecycleEvent,
    LedgerEntry,
    LifecycleRecordOutcome,
    LifecycleRecordResult,
    LifecycleStage,
    LifecycleTotals,
    UsageEvent,
    UsageOutcome,
    utc_now,
)


class ContextLedger:
    """Tracks what the engine selected, returned, and what the host reported.

    The ledger does **not** infer what sits in an agent's opaque context window.
    ``REPORTED_USED`` and agent feedback are recorded only when the host sends them.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, list[LedgerEntry]] = {}

    def record_lifecycle(
        self,
        event: ContextLifecycleEvent,
        *,
        dedupe: bool = True,
    ) -> LifecycleRecordResult:
        entries = self._sessions.setdefault(event.session_id, [])
        entry = self._get_or_create_entry(entries, event.item_id, event.version)
        now = event.recorded_at

        if event.stage == LifecycleStage.SELECTED:
            return self._record_selected(entry, event, dedupe, now)
        if event.stage == LifecycleStage.RETURNED:
            self._apply_version_supersession(entries, event.item_id, event.version, now)
            return self._record_returned(entry, event, dedupe, now)
        if event.stage == LifecycleStage.REPORTED_USED:
            return self._record_reported_used(entry, event, dedupe, now)

        return LifecycleRecordResult(
            event=event,
            outcome=LifecycleRecordOutcome.RECORDED,
            message="unknown stage",
        )

    def record_feedback(self, event: UsageEvent) -> None:
        """Host-provided quality signals (not lifecycle stage)."""
        entries = self._sessions.setdefault(event.session_id, [])
        entry = self._get_or_create_entry(entries, event.item_id, event.version)
        if event.outcome in (
            UsageOutcome.AGENT_FEEDBACK_POSITIVE,
            UsageOutcome.AGENT_FEEDBACK_NEGATIVE,
        ):
            entry.agent_feedback.append(event.outcome)

    def record(self, event: UsageEvent) -> LifecycleRecordResult | None:
        """Backward-compatible usage recording; maps legacy outcomes to lifecycle."""
        if event.outcome == UsageOutcome.DELIVERED:
            return self.record_lifecycle(
                ContextLifecycleEvent(
                    session_id=event.session_id,
                    item_id=event.item_id,
                    version=event.version,
                    stage=LifecycleStage.RETURNED,
                    detail=event.detail,
                    recorded_at=event.recorded_at,
                )
            )
        if event.outcome == UsageOutcome.SKIPPED_DUPLICATE:
            return None
        if event.outcome in (
            UsageOutcome.AGENT_FEEDBACK_POSITIVE,
            UsageOutcome.AGENT_FEEDBACK_NEGATIVE,
        ):
            self.record_feedback(event)
            return None
        return None

    def status(self, session_id: str) -> ContextEngineStatus:
        entries = self._sessions.get(session_id, [])
        totals = LifecycleTotals(
            selected=sum(e.selected_count for e in entries),
            returned=sum(e.returned_count for e in entries),
            reported_used=sum(e.reported_used_count for e in entries),
            duplicate_select_skips=sum(e.duplicate_select_skips for e in entries),
            duplicate_return_skips=sum(e.duplicate_return_skips for e in entries),
        )
        return ContextEngineStatus(
            session_id=session_id,
            entries=list(entries),
            totals=totals,
        )

    def was_returned(self, session_id: str, item_id: str, version: str) -> bool:
        entry = self._find_entry(session_id, item_id, version)
        return entry is not None and entry.returned_count > 0

    def was_selected(self, session_id: str, item_id: str, version: str) -> bool:
        entry = self._find_entry(session_id, item_id, version)
        return entry is not None and entry.selected_count > 0

    def was_delivered(self, session_id: str, item_id: str, version: str) -> bool:
        """Alias for ``was_returned`` (legacy adapter name)."""
        return self.was_returned(session_id, item_id, version)

    def _find_entry(
        self,
        session_id: str,
        item_id: str,
        version: str,
    ) -> LedgerEntry | None:
        for entry in self._sessions.get(session_id, []):
            if entry.item_id == item_id and entry.version == version:
                return entry
        return None

    def _get_or_create_entry(
        self,
        entries: list[LedgerEntry],
        item_id: str,
        version: str,
    ) -> LedgerEntry:
        existing = next(
            (e for e in entries if e.item_id == item_id and e.version == version),
            None,
        )
        if existing:
            return existing
        entry = LedgerEntry(item_id=item_id, version=version)
        entries.append(entry)
        return entry

    def _record_selected(
        self,
        entry: LedgerEntry,
        event: ContextLifecycleEvent,
        dedupe: bool,
        now,
    ) -> LifecycleRecordResult:
        if entry.selected_count > 0 and dedupe:
            entry.duplicate_select_skips += 1
            return LifecycleRecordResult(
                event=event,
                outcome=LifecycleRecordOutcome.DUPLICATE_SKIPPED,
                message="Already selected for this session and version.",
            )
        entry.selected_count += 1
        if entry.first_selected_at is None:
            entry.first_selected_at = now
        entry.last_selected_at = now
        return LifecycleRecordResult(event=event, outcome=LifecycleRecordOutcome.RECORDED)

    def _record_returned(
        self,
        entry: LedgerEntry,
        event: ContextLifecycleEvent,
        dedupe: bool,
        now,
    ) -> LifecycleRecordResult:
        if entry.returned_count > 0 and dedupe:
            entry.duplicate_return_skips += 1
            return LifecycleRecordResult(
                event=event,
                outcome=LifecycleRecordOutcome.DUPLICATE_SKIPPED,
                message="Already returned for this session and version.",
            )
        entry.returned_count += 1
        if entry.first_returned_at is None:
            entry.first_returned_at = now
        entry.last_returned_at = now
        return LifecycleRecordResult(event=event, outcome=LifecycleRecordOutcome.RECORDED)

    def _record_reported_used(
        self,
        entry: LedgerEntry,
        event: ContextLifecycleEvent,
        dedupe: bool,
        now,
    ) -> LifecycleRecordResult:
        if entry.reported_used_count > 0 and dedupe:
            return LifecycleRecordResult(
                event=event,
                outcome=LifecycleRecordOutcome.DUPLICATE_SKIPPED,
                message="Host already reported this item as used for this version.",
            )
        entry.reported_used_count += 1
        if entry.first_reported_used_at is None:
            entry.first_reported_used_at = now
        entry.last_reported_used_at = now
        return LifecycleRecordResult(event=event, outcome=LifecycleRecordOutcome.RECORDED)

    def _apply_version_supersession(
        self,
        entries: list[LedgerEntry],
        item_id: str,
        new_version: str,
        now,
    ) -> None:
        for entry in entries:
            if entry.item_id != item_id or entry.version == new_version:
                continue
            if entry.superseded:
                continue
            if entry.returned_count > 0 or entry.selected_count > 0:
                entry.superseded = True
                entry.superseded_by_version = new_version
                entry.superseded_at = now
