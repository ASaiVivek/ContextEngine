from pathlib import Path

from context_engine.catalog import load_catalog, read_item_content


def test_load_catalog(repo_knowledge_root: Path) -> None:
    catalog = load_catalog(repo_knowledge_root)
    assert len(catalog.items) >= 3
    assert catalog.get("payments/idempotency") is not None


def test_read_markdown(repo_knowledge_root: Path) -> None:
    catalog = load_catalog(repo_knowledge_root)
    item = catalog.get("payments/retry-policy")
    assert item is not None
    text = read_item_content(repo_knowledge_root, item)
    assert "exponential backoff" in text.lower()
