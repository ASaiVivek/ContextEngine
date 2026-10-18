"""Load and query the versioned knowledge catalog."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class CatalogItemRef(BaseModel):
    id: str
    path: str
    version: str
    domain: str | None = None
    tags: list[str] = Field(default_factory=list)
    summary: str | None = None


class KnowledgeCatalog(BaseModel):
    version: str
    items: list[CatalogItemRef]

    def get(self, item_id: str) -> CatalogItemRef | None:
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def list_ids(self) -> list[str]:
        return [item.id for item in self.items]


def default_knowledge_root() -> Path:
    """Resolve knowledge/ relative to repo root (cwd or package parent)."""
    candidates = [
        Path.cwd() / "knowledge",
        Path(__file__).resolve().parents[2] / "knowledge",
    ]
    for path in candidates:
        if (path / "catalog.yaml").is_file():
            return path
    return candidates[0]


def load_catalog(knowledge_root: Path | None = None) -> KnowledgeCatalog:
    root = knowledge_root or default_knowledge_root()
    catalog_path = root / "catalog.yaml"
    if not catalog_path.is_file():
        raise FileNotFoundError(f"Catalog not found: {catalog_path}")

    raw = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    items = [CatalogItemRef.model_validate(entry) for entry in raw.get("items", [])]
    return KnowledgeCatalog(version=str(raw.get("version", "1")), items=items)


def read_item_content(knowledge_root: Path, catalog_item: CatalogItemRef) -> str:
    path = knowledge_root / catalog_item.path
    if not path.is_file():
        raise FileNotFoundError(f"Knowledge file not found: {path}")
    return path.read_text(encoding="utf-8")
