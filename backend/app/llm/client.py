"""The LLM call: LiteLLM -> OpenRouter -> Cerebras (PLAN.md §9).

`generate_response` is the single entry point and never raises for a bad model
response — a malformed or failed completion degrades into a plain apology
message with no actions, so one bad generation can't take down the chat
endpoint (PLAN.md §12: graceful handling of malformed responses).
"""

from __future__ import annotations

import logging

from litellm import completion

from .schemas import LLMResponseError, LLMStructuredResponse, parse_structured_response

logger = logging.getLogger(__name__)

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}

SYSTEM_PROMPT = """You are FinAlly, an AI trading assistant embedded in a simulated \
trading workstation. The portfolio is virtual money — trades you request are executed \
immediately against a paper account with no fees and instant fill at the current market price.

Your job:
- Analyze the portfolio's composition, risk concentration, and unrealized P&L.
- Suggest trades with brief, concrete reasoning grounded in the data you are given.
- Execute trades when the user asks for them or agrees to a suggestion, by putting them \
in the `trades` array.
- Manage the watchlist proactively via `watchlist_changes` when a ticker becomes relevant \
to the conversation.
- Be concise and data-driven. Cite actual numbers from the portfolio context. No filler.

Rules:
- Only reference prices that appear in the portfolio context. Never invent a price.
- Only place a trade when the user's intent is clear. Do not trade on speculation.
- `side` is "buy" or "sell"; `action` is "add" or "remove"; `quantity` is a positive number \
of shares (fractional shares are allowed).
- Multiple trades execute sequentially in array order against the account state left by the \
previous one, so order them deliberately (sell before buy if the cash is needed).
- Always respond with valid JSON matching the required schema. `message` is the only \
required field; leave `trades` and `watchlist_changes` empty when no action is warranted."""


def build_messages(
    user_message: str,
    portfolio_context: str,
    history: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Assemble system prompt, portfolio context, prior turns, and the new message."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": portfolio_context},
        *history,
        {"role": "user", "content": user_message},
    ]


def generate_response(
    user_message: str,
    portfolio_context: str,
    history: list[dict[str, str]],
) -> LLMStructuredResponse:
    """Call the model and return its parsed structured response.

    Any failure — network, provider, or unparseable output — is logged and
    converted into a response that says so, carrying no actions.
    """
    messages = build_messages(user_message, portfolio_context, history)
    try:
        response = completion(
            model=MODEL,
            messages=messages,
            response_format=LLMStructuredResponse,
            reasoning_effort="low",
            extra_body=EXTRA_BODY,
        )
        return parse_structured_response(response.choices[0].message.content)
    except LLMResponseError:
        logger.exception("LLM returned an unusable structured response")
        return LLMStructuredResponse(
            message="I got a garbled response from the model. Could you rephrase that?"
        )
    except Exception:
        logger.exception("LLM call failed")
        return LLMStructuredResponse(
            message="I couldn't reach the model just now. Please try again in a moment."
        )
