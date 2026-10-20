from context_engine.models import (
    ContextLifecycleEvent,
    GetRequest,
    LifecycleStage,
    RecordLifecycleRequest,
    RecordUsageRequest,
    ResolveRequest,
    UsageEvent,
    UsageOutcome,
)


def test_legacy_record_usage_maps_to_returned(engine) -> None:
    engine.record_usage(
        RecordUsageRequest(
            events=[
                UsageEvent(
                    session_id="ledger-1",
                    item_id="payments/idempotency",
                    version="1.0.0",
                    outcome=UsageOutcome.DELIVERED,
                )
            ]
        )
    )
    status = engine.get_status("ledger-1")
    assert status.total_deliveries == 1
    assert status.totals.returned == 1
    assert status.entries[0].item_id == "payments/idempotency"


def test_resolve_records_selected(engine) -> None:
    engine.resolve(
        ResolveRequest(
            session_id="life-1",
            task_description="payment idempotency retry",
            domain="payments",
        )
    )
    status = engine.get_status("life-1")
    assert status.totals.selected >= 1
    assert status.totals.returned == 0


def test_get_records_returned(engine) -> None:
    engine.get(
        GetRequest(
            session_id="life-2",
            item_ids=["payments/idempotency"],
        )
    )
    status = engine.get_status("life-2")
    assert status.totals.returned == 1
    assert status.totals.selected == 0


def test_host_reported_used_is_explicit(engine) -> None:
    engine.record_lifecycle(
        RecordLifecycleRequest(
            events=[
                ContextLifecycleEvent(
                    session_id="life-3",
                    item_id="payments/idempotency",
                    version="1.0.0",
                    stage=LifecycleStage.REPORTED_USED,
                    detail="host_callback",
                )
            ]
        )
    )
    status = engine.get_status("life-3")
    assert status.totals.reported_used == 1
    assert status.totals.returned == 0
    assert "host signals" in status.observation_scope.lower()
