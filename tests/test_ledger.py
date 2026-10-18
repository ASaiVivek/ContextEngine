from context_engine.models import RecordUsageRequest, UsageEvent, UsageOutcome


def test_record_usage_and_status(engine) -> None:
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
    assert status.entries[0].item_id == "payments/idempotency"
