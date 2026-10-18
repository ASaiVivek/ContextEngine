from pathlib import Path

import pytest

from context_engine.api import ContextEngine


@pytest.fixture
def repo_knowledge_root() -> Path:
    root = Path(__file__).resolve().parents[1] / "knowledge"
    assert (root / "catalog.yaml").is_file()
    return root


@pytest.fixture
def engine(repo_knowledge_root: Path) -> ContextEngine:
    return ContextEngine(knowledge_root=repo_knowledge_root)
