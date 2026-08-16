"""Structured output parsing: valid shapes accepted, malformed ones rejected cleanly."""

import pytest

from app.llm.schemas import LLMResponseError, parse_structured_response


def test_message_only_defaults_to_no_actions():
    response = parse_structured_response('{"message": "All good."}')
    assert response.message == "All good."
    assert response.trades == []
    assert response.watchlist_changes == []


def test_full_schema():
    raw = """
    {
      "message": "Buying Apple and watching PayPal.",
      "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
      "watchlist_changes": [{"ticker": "PYPL", "action": "add"}]
    }
    """
    response = parse_structured_response(raw)
    assert response.trades[0].ticker == "AAPL"
    assert response.trades[0].quantity == 10.0
    assert response.watchlist_changes[0].action == "add"


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "   ",
        "not json at all",
        "{",
        '{"trades": []}',  # missing required `message`
        '{"message": "x", "trades": [{"ticker": "AAPL", "side": "hold", "quantity": 1}]}',
        '{"message": "x", "watchlist_changes": [{"ticker": "AAPL", "action": "star"}]}',
        '["message"]',
    ],
)
def test_malformed_responses_raise_llm_response_error(raw):
    with pytest.raises(LLMResponseError):
        parse_structured_response(raw)
