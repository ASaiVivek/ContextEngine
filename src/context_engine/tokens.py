"""Deterministic token estimates for budget enforcement."""

from __future__ import annotations


def estimate_tokens(text: str) -> int:
    """Approximate tokens with a stable, explainable heuristic (chars / 4)."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def candidate_payload_tokens(
    item_id: str,
    version: str,
    reasons: list[str],
    summary: str | None,
    content: str | None,
) -> int:
    """Tokens counted toward max_tokens for one resolve result row."""
    parts = [item_id, version, *reasons]
    if summary:
        parts.append(summary)
    if content:
        parts.append(content)
    return estimate_tokens("\n".join(parts))
