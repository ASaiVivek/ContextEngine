from context_engine.models import (
    ContextLifecycleEvent,
    GetRequest,
    LifecycleRecordOutcome,
    LifecycleStage,
    RecordLifecycleRequest,
    ResolveRequest,
)


def test_repeated_resolve_dedupes_selection(engine) -> None:
    request = ResolveRequest(
        session_id="repeat-select",
        task_description="payment idempotency retry backoff",
        domain="payments",
    )
    engine.resolve(request)
    first = engine.get_status("repeat-select")
    engine.resolve(request)
    second = engine.get_status("repeat-select")
    assert second.totals.selected == first.totals.selected
    assert second.totals.duplicate_select_skips > first.totals.duplicate_select_skips


def test_repeated_get_dedupes_return(engine) -> None:
    get_req = GetRequest(session_id="repeat-return", item_ids=["payments/idempotency"])
    engine.get(get_req)
    engine.get(get_req)
    status = engine.get_status("repeat-return")
    assert status.totals.returned == 1
    assert status.totals.duplicate_return_skips == 1


def test_filter_undelivered_uses_returned_not_selected(engine) -> None:
    from context_engine.models import ResolveRequest

    response = engine.resolve(
        ResolveRequest(
            session_id="filter-session",
            task_description="payment idempotency",
            domain="payments",
        )
    )
    before = engine.filter_undelivered("filter-session", response.candidates)
    assert len(before) == len(response.candidates)

    engine.get(
        GetRequest(
            session_id="filter-session",
            item_ids=[response.candidates[0].item_id],
        )
    )
    after = engine.filter_undelivered("filter-session", response.candidates)
    assert len(after) == len(response.candidates) - 1


def test_version_change_supersedes_prior_entry(engine) -> None:
    session = "version-session"
    engine.record_lifecycle(
        RecordLifecycleRequest(
            events=[
                ContextLifecycleEvent(
                    session_id=session,
                    item_id="payments/idempotency",
                    version="1.0.0",
                    stage=LifecycleStage.RETURNED,
                )
            ]
        )
    )
    engine.record_lifecycle(
        RecordLifecycleRequest(
            events=[
                ContextLifecycleEvent(
                    session_id=session,
                    item_id="payments/idempotency",
                    version="2.0.0",
                    stage=LifecycleStage.RETURNED,
                )
            ]
        )
    )
    status = engine.get_status(session)
    old = next(e for e in status.entries if e.version == "1.0.0")
    new = next(e for e in status.entries if e.version == "2.0.0")
    assert old.superseded is True
    assert old.superseded_by_version == "2.0.0"
    assert new.returned_count == 1


def test_sessions_are_isolated(engine) -> None:
    engine.get(
        GetRequest(session_id="session-a", item_ids=["payments/idempotency"])
    )
    status_b = engine.get_status("session-b")
    assert status_b.totals.returned == 0


def test_record_lifecycle_returns_duplicate_outcome(engine) -> None:
    event = ContextLifecycleEvent(
        session_id="dup-report",
        item_id="payments/idempotency",
        version="1.0.0",
        stage=LifecycleStage.REPORTED_USED,
    )
    first = engine.record_lifecycle(RecordLifecycleRequest(events=[event]))
    second = engine.record_lifecycle(RecordLifecycleRequest(events=[event]))
    assert first.results[0].outcome == LifecycleRecordOutcome.RECORDED
    assert second.results[0].outcome == LifecycleRecordOutcome.DUPLICATE_SKIPPED
