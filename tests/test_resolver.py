from context_engine.api import ContextEngine
from context_engine.models import ResolveRequest


def test_resolve_payments_task(engine: ContextEngine) -> None:
    response = engine.resolve(
        ResolveRequest(
            session_id="test-session",
            task_description="Implement idempotent payment API retries with backoff",
            domain="payments",
        )
    )
    ids = [c.item_id for c in response.candidates]
    assert "payments/idempotency" in ids
    assert "payments/retry-policy" in ids
    assert response.candidates[0].score >= response.candidates[-1].score


def test_resolve_infra_not_top_for_payments(engine: ContextEngine) -> None:
    response = engine.resolve(
        ResolveRequest(
            session_id="s2",
            task_description="Fix ECS rolling deployment for payment service",
            domain="infrastructure",
        )
    )
    ids = [c.item_id for c in response.candidates]
    assert "infrastructure/ecs-deployment" in ids
