"""Session ledger: what was supplied and usage feedback."""

from __future__ import annotations

from context_engine.models import (
    ContextEngineStatus,
    LedgerEntry,
    UsageEvent,
    UsageOutcome,
    utc_now,
)


class ContextLedger:
    def __init__(self) -> None:
        self._sessions: dict[str, list[LedgerEntry]] = {}

    def record(self, event: UsageEvent) -> None:
        entries = self._sessions.setdefault(event.session_id, [])
        existing = next(
            (e for e in entries if e.item_id == event.item_id and e.version == event.version),
            None,
        )
        now = event.recorded_at
        if existing:
            existing.last_delivered_at = now
            if event.outcome == UsageOutcome.DELIVERED:
                existing.delivery_count += 1
            existing.outcomes.append(event.outcome)
            return

        entries.append(
            LedgerEntry(
                item_id=event.item_id,
                version=event.version,
                first_delivered_at=now,
                last_delivered_at=now,
                delivery_count=1 if event.outcome == UsageOutcome.DELIVERED else 0,
                outcomes=[event.outcome],
            )
        )

    def status(self, session_id: str) -> ContextEngineStatus:
        entries = self._sessions.get(session_id, [])
        total = sum(e.delivery_count for e in entries)
        return ContextEngineStatus(
            session_id=session_id,
            entries=list(entries),
            total_deliveries=total,
        )

    def was_delivered(self, session_id: str, item_id: str, version: str) -> bool:
        for entry in self._sessions.get(session_id, []):
            if entry.item_id == item_id and entry.version == version:
                if UsageOutcome.DELIVERED in entry.outcomes:
                    return True
        return False
