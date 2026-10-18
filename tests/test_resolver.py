from context_engine.api import ContextEngine
from context_engine.models import (
    ContextBudget,
    DomainFilterMode,
    ResolveRequest,
    ResolveStatus,
)
from context_engine.catalog import load_catalog
from context_engine.resolver import resolve_candidates


def test_resolve_payments_task(engine: ContextEngine) -> None:
    response = engine.resolve(
        ResolveRequest(
            session_id="test-session",
            task_description="Implement idempotent payment API retries with backoff",
            domain="payments",
        )
    )
    assert response.status == ResolveStatus.MATCHED
    ids = [c.item_id for c in response.candidates]
    assert "payments/idempotency" in ids
    assert "payments/retry-policy" in ids
    assert response.candidates[0].score >= response.candidates[-1].score
    top = response.candidates[0]
    assert top.version
    assert top.reasons
    assert top.content is not None
    assert "Idempotency" in top.content or "retry" in top.content.lower()


def test_resolve_infra_domain_hint(engine: ContextEngine) -> None:
    response = engine.resolve(
        ResolveRequest(
            session_id="s2",
            task_description="Fix ECS rolling deployment for payment service",
            domain="infrastructure",
        )
    )
    ids = [c.item_id for c in response.candidates]
    assert "infrastructure/ecs-deployment" in ids


def test_domain_restrict_excludes_other_domains(engine: ContextEngine) -> None:
    response = engine.resolve(
        ResolveRequest(
            session_id="s3",
            task_description="idempotent retry backoff payment API",
            domain="payments",
            domain_filter=DomainFilterMode.RESTRICT,
        )
    )
    assert response.status == ResolveStatus.MATCHED
    assert all(c.item_id.startswith("payments/") for c in response.candidates)


def test_domain_restrict_empty_catalog_domain(engine: ContextEngine) -> None:
    response = engine.resolve(
        ResolveRequest(
            session_id="s4",
            task_description="deploy ecs service",
            domain="nonexistent-domain",
            domain_filter=DomainFilterMode.RESTRICT,
        )
    )
    assert response.status == ResolveStatus.DOMAIN_EMPTY
    assert response.candidates == []
    assert response.message is not None


def test_no_match_returns_explicit_status(engine: ContextEngine) -> None:
    response = engine.resolve(
        ResolveRequest(
            session_id="s5",
            task_description="xyzzy plugh completely unrelated tokens",
        )
    )
    assert response.status == ResolveStatus.NO_MATCH
    assert response.candidates == []
    assert response.message is not None


def test_ranking_is_deterministic(engine: ContextEngine) -> None:
    request = ResolveRequest(
        session_id="det",
        task_description="payment idempotency retry policy",
        domain="payments",
    )
    first = engine.resolve(request)
    second = engine.resolve(request)
    assert [c.model_dump() for c in first.candidates] == [
        c.model_dump() for c in second.candidates
    ]


def test_max_items_budget(engine: ContextEngine) -> None:
    response = engine.resolve(
        ResolveRequest(
            session_id="budget-items",
            task_description="payment idempotency retry ecs deployment",
            budget=ContextBudget(max_items=1),
        )
    )
    assert len(response.candidates) == 1


def test_max_tokens_budget(engine: ContextEngine) -> None:
    query = ResolveRequest(
        session_id="budget-tokens-full",
        task_description="payment idempotency retry policy backoff",
        include_content=False,
    )
    full = engine.resolve(query)
    tight = engine.resolve(
        ResolveRequest(
            session_id="budget-tokens",
            task_description="payment idempotency retry policy backoff",
            include_content=False,
            budget=ContextBudget(max_tokens=80),
        )
    )
    assert len(full.candidates) >= 1
    assert len(tight.candidates) <= len(full.candidates)
    assert len(tight.candidates) >= 1


def test_missing_metadata_still_ranks(tmp_path, monkeypatch) -> None:
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    docs = knowledge / "sparse.md"
    docs.write_text("# Sparse\n\nuniquekeyword alpha beta gamma\n", encoding="utf-8")
    (knowledge / "catalog.yaml").write_text(
        """
version: "9"
items:
  - id: sparse/item
    path: sparse.md
    version: "2.0.0"
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    catalog = load_catalog(knowledge)
    result = resolve_candidates(
        catalog,
        knowledge,
        ResolveRequest(
            session_id="sparse",
            task_description="uniquekeyword alpha",
            include_content=True,
        ),
    )
    assert result.status == ResolveStatus.MATCHED
    assert result.candidates[0].item_id == "sparse/item"
    assert result.candidates[0].version == "2.0.0"
    assert result.candidates[0].content is not None


def test_version_change_reflected_in_candidates(tmp_path, monkeypatch) -> None:
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    doc = knowledge / "v.md"
    doc.write_text("# Version doc\n\nversiontoken\n", encoding="utf-8")
    catalog_path = knowledge / "catalog.yaml"

    def write_catalog(version: str) -> None:
        catalog_path.write_text(
            f"""
version: "cat-1"
items:
  - id: demo/v
    path: v.md
    version: "{version}"
    summary: versiontoken summary
""",
            encoding="utf-8",
        )

    write_catalog("1.0.0")
    monkeypatch.chdir(tmp_path)
    catalog = load_catalog(knowledge)
    r1 = resolve_candidates(
        catalog,
        knowledge,
        ResolveRequest(session_id="v", task_description="versiontoken"),
    )
    assert r1.candidates[0].version == "1.0.0"

    write_catalog("2.1.0")
    catalog = load_catalog(knowledge)
    r2 = resolve_candidates(
        catalog,
        knowledge,
        ResolveRequest(session_id="v", task_description="versiontoken"),
    )
    assert r2.candidates[0].version == "2.1.0"


def test_explainable_reasons_include_score_total(engine: ContextEngine) -> None:
    response = engine.resolve(
        ResolveRequest(
            session_id="explain",
            task_description="idempotency payment",
            domain="payments",
        )
    )
    assert response.candidates
    assert any(r.startswith("score_total:") for r in response.candidates[0].reasons)
