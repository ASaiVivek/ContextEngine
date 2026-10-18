from context_engine.tokens import estimate_tokens, candidate_payload_tokens


def test_estimate_tokens_is_deterministic() -> None:
    text = "hello world " * 10
    assert estimate_tokens(text) == estimate_tokens(text)
    assert estimate_tokens("") == 0


def test_candidate_payload_tokens_counts_fields() -> None:
    small = candidate_payload_tokens("a/b", "1.0", ["r"], "sum", "body")
    large = candidate_payload_tokens("a/b", "1.0", ["r"], "sum", "body" * 100)
    assert large > small
