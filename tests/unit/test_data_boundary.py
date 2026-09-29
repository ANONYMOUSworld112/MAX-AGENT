import pytest
from core.max_infra.data_boundary import DataBoundary

def test_data_boundary_scrub_api_keys():
    boundary = DataBoundary()
    raw = "My key is sk-1234567890abcdef1234567890abcdef and google key is AIzaSyD1234567890abcdefghijklmnopqr"
    res = boundary.scrub(raw)

    assert "sk-1234567890abcdef1234567890abcdef" not in res.scrubbed_text
    assert "AIzaSyD1234567890abcdefghijklmnopqr" not in res.scrubbed_text
    assert "[REDACTED_API_KEY" in res.scrubbed_text
    assert len(res.token_map) == 2

    # Unscrub restores exact string
    restored = boundary.unscrub(res.scrubbed_text, res.token_map)
    assert restored == raw

def test_data_boundary_scrub_pii():
    boundary = DataBoundary()
    raw = "Contact ceo@anthropic.com or call 4111-2222-3333-4444"
    res = boundary.scrub(raw)

    assert "ceo@anthropic.com" not in res.scrubbed_text
    assert "4111-2222-3333-4444" not in res.scrubbed_text
    assert "[REDACTED_EMAIL" in res.scrubbed_text
    assert "[REDACTED_CREDIT_CARD" in res.scrubbed_text
