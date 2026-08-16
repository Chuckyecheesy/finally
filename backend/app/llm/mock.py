"""Deterministic offline responder used when `LLM_MOCK=true` (PLAN.md §5, §12).

Never touches the network. The same input always produces the same structured
response, which is what makes it usable from both backend unit tests and the
Playwright E2E suite.

SUPPORTED TRIGGER PHRASES (all matching is case-insensitive)
-----------------------------------------------------------
Trades — matched anywhere in the message, every match becomes a trade, in the
order they appear. Both of these forms work, for "buy" and for "sell":

    buy 10 AAPL
    buy 10 shares of AAPL
    sell 2.5 TSLA
    sell 2.5 shares of TSLA

Quantity may be an integer or a decimal. The ticker is 1-5 letters.

Watchlist — matched anywhere in the message, every match becomes a change:

    add NFLX to watchlist          (also "to my watchlist")
    watch NFLX
    remove NFLX from watchlist     (also "from my watchlist")
    unwatch NFLX

Portfolio summary — if the message contains any of these substrings and no
trade or watchlist phrase matched, the reply is the portfolio context prefixed
with "Here's your portfolio:" and carries no actions:

    portfolio, position, holdings, p&l, pnl, how am i doing

Fallback — anything else returns MOCK_FALLBACK_MESSAGE with no actions.
"""

from __future__ import annotations

import re

from app.market import normalize_ticker

from .schemas import LLMStructuredResponse, TradeAction, WatchlistChange

MOCK_ENV_VAR = "LLM_MOCK"

PORTFOLIO_PREFIX = "Here's your portfolio:"
MOCK_FALLBACK_MESSAGE = (
    "I'm FinAlly, your trading assistant. Ask me about your portfolio, or tell me to "
    "buy or sell shares and I'll execute it."
)

_TRADE_RE = re.compile(
    r"\b(?P<side>buy|sell)\s+(?P<quantity>\d+(?:\.\d+)?)\s+(?:shares?\s+of\s+)?(?P<ticker>[a-z]{1,5})\b",
    re.IGNORECASE,
)
_WATCH_ADD_RE = re.compile(
    r"\badd\s+(?P<ticker>[a-z]{1,5})\s+to\s+(?:my\s+)?watchlist\b|\bwatch\s+(?P<alt>[a-z]{1,5})\b",
    re.IGNORECASE,
)
_WATCH_REMOVE_RE = re.compile(
    r"\bremove\s+(?P<ticker>[a-z]{1,5})\s+from\s+(?:my\s+)?watchlist\b|\bunwatch\s+(?P<alt>[a-z]{1,5})\b",
    re.IGNORECASE,
)

_PORTFOLIO_KEYWORDS = ("portfolio", "position", "holdings", "p&l", "pnl", "how am i doing")


def _watchlist_changes(message: str, pattern: re.Pattern[str], action: str) -> list[WatchlistChange]:
    changes = []
    for match in pattern.finditer(message):
        ticker = match.group("ticker") or match.group("alt")
        changes.append(WatchlistChange(ticker=normalize_ticker(ticker), action=action))
    return changes


def generate_response(
    user_message: str,
    portfolio_context: str,
    history: list[dict[str, str]],
) -> LLMStructuredResponse:
    """Mirror of `client.generate_response`, resolved entirely from the message text.

    `history` is accepted for signature compatibility and deliberately ignored —
    the mock stays stateless so a test's assertions don't depend on how many
    messages ran before it.
    """
    trades = [
        TradeAction(
            ticker=normalize_ticker(match.group("ticker")),
            side=match.group("side").lower(),
            quantity=float(match.group("quantity")),
        )
        for match in _TRADE_RE.finditer(user_message)
    ]
    # "watch" also matches inside "watchlist", so removals are matched first and
    # their spans blanked out before the add pattern runs.
    removals = _watchlist_changes(user_message, _WATCH_REMOVE_RE, "remove")
    add_source = _WATCH_REMOVE_RE.sub(" ", user_message)
    additions = _watchlist_changes(add_source, _WATCH_ADD_RE, "add")
    changes = removals + additions

    if trades or changes:
        parts = [f"{t.side}ing {t.quantity:g} {t.ticker}" for t in trades]
        parts += [f"{c.action}ing {c.ticker} {'to' if c.action == 'add' else 'from'} your watchlist" for c in changes]
        message = "Done — " + ", ".join(parts) + "."
        return LLMStructuredResponse(message=message, trades=trades, watchlist_changes=changes)

    lowered = user_message.lower()
    if any(keyword in lowered for keyword in _PORTFOLIO_KEYWORDS):
        return LLMStructuredResponse(message=f"{PORTFOLIO_PREFIX}\n\n{portfolio_context}")

    return LLMStructuredResponse(message=MOCK_FALLBACK_MESSAGE)
