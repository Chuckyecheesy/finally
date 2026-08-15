# Massive API (formerly Polygon.io) — Research Notes

Massive.com is the 2026 rebrand of Polygon.io. The API surface, endpoints, and
API keys are unchanged from Polygon.io — only the marketing/docs domain moved
(`polygon.io` → `massive.com`). This document summarizes what FinAlly needs:
real-time-ish and end-of-day prices for a small, dynamic set of tickers.

## Authentication

Every request needs an API key, passed either as a query parameter or a
bearer token:

```
GET https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers?apiKey=YOUR_KEY
```

```
Authorization: Bearer YOUR_KEY
```

The base host for REST calls remains `api.polygon.io` regardless of the
`massive.com` docs rebrand. FinAlly reads the key from the `MASSIVE_API_KEY`
environment variable (see `planning/PLAN.md` §5).

## Rate Limits

| Plan | Limit |
|---|---|
| Free | 5 requests/minute |
| Paid (Starter/Developer/Advanced) | No hard cap; recommended to stay under ~100 req/s |

Free tier is the one to design around by default, since course students won't
have a paid key. At 5 req/min, one call every **15 seconds** is the safe poll
interval — this is what `planning/PLAN.md` §6 specifies.

## Endpoints Relevant to FinAlly

### 1. Full Market Snapshot (real-time-ish, multiple tickers in one call)

```
GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,GOOGL,MSFT&apiKey=YOUR_KEY
```

This is the endpoint that matters most: it returns the latest trade, latest
quote, today's change, and the previous day's bar for a **comma-separated
list of tickers in a single request** — exactly what's needed to refresh an
entire watchlist with one API call per poll interval, which is essential for
staying under the free-tier 5 req/min limit regardless of watchlist size.

- `tickers` (optional, case-sensitive, comma-separated) — omit to get the
  entire market (10,000+ tickers); FinAlly always passes the current
  watchlist explicitly.
- `include_otc` (optional, bool) — default `false`.
- Data recency: 15-minute delayed or real-time depending on plan tier. On the
  free tier, expect delayed data — fine for a simulated-money demo app.
- Snapshot data resets daily around 3:30 AM ET and repopulates as exchanges
  report, starting ~4:00 AM ET. Outside market hours (pre-market before that
  reset, or on a day with no trades yet), a ticker's snapshot may be stale or
  partially empty.

Key response fields (per ticker, under `tickers[]`):

```json
{
  "ticker": "AAPL",
  "lastTrade": { "p": 190.45, "t": 1700000000000000000 },
  "lastQuote": { "p": 190.44, "P": 190.46, "t": 1700000000000000000 },
  "prevDay": { "o": 188.0, "h": 191.0, "l": 187.5, "c": 189.90, "v": 54000000 },
  "day": { "o": 189.9, "h": 191.2, "l": 189.5, "c": 190.45, "v": 12000000 },
  "todaysChange": 0.55,
  "todaysChangePerc": 0.29,
  "updated": 1700000000000000000
}
```

Notes:
- `lastTrade.t` / `updated` are **Unix nanoseconds**, not seconds or
  milliseconds — divide by `1e9` to get Unix seconds.
- `lastTrade.p` is the field to use as "current price."
- The official Python client's `LastTrade` model (`massive.rest.models.trades.LastTrade`)
  maps JSON field `t` to an attribute called **`sip_timestamp`**, not
  `timestamp` — there is no `.timestamp` attribute on this model. FinAlly's
  `massive_client.py` previously read `snap.last_trade.timestamp`, which
  raised `AttributeError` on every real snapshot and was silently caught, so
  live Massive polling never updated the price cache. This is fixed — see the
  "Resolved: Massive Timestamp Field" section of `MARKET_INTERFACE.md`.
- A ticker with no trades yet today (e.g., pre-market, or an obscure symbol)
  may be missing `lastTrade` or `day` entirely — code must not assume these
  keys are always present.

### 2. Previous Day Bar (single-ticker EOD)

```
GET /v2/aggs/ticker/{ticker}/prev?apiKey=YOUR_KEY
```

Returns the previous completed trading day's OHLCV bar for one ticker. Useful
as a fallback "last known price" when a snapshot has no trade data yet, or
for computing a daily % change baseline independent of the snapshot's
`prevDay` field.

### 3. Grouped Daily Bars (EOD, whole market in one call)

```
GET /v2/aggs/grouped/locale/us/market/stocks/{date}/apiKey=YOUR_KEY
```

Returns OHLC for **every** US ticker on a given trading date. Not needed for
FinAlly's live-watchlist use case (the snapshot endpoint already batches by
ticker list), but worth knowing about if a future feature needs bulk
end-of-day history across the market rather than per-ticker.

### 4. Custom Aggregates / Bars (historical minute/day bars, single ticker)

```
GET /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}?apiKey=YOUR_KEY
```

`timespan` is `minute`, `hour`, `day`, etc. Useful if FinAlly ever wants to
seed a chart with historical bars instead of only accumulating from the SSE
stream — not currently used, since the frontend chart is built by
accumulating live prices client-side (per `planning/PLAN.md` §10).

## Official Python Client

```bash
pip install -U massive
# or, in this project: uv add massive
```

```python
from massive import RESTClient
from massive.rest.models import SnapshotMarketType

client = RESTClient(api_key="YOUR_KEY")

# Multi-ticker snapshot — the call FinAlly's poller uses
snapshots = client.get_snapshot_all(
    market_type=SnapshotMarketType.STOCKS,
    tickers=["AAPL", "GOOGL", "MSFT"],
)
for snap in snapshots:
    # NB: `sip_timestamp`, not `timestamp` — and it's Unix nanoseconds
    print(snap.ticker, snap.last_trade.price, snap.last_trade.sip_timestamp / 1e9)
```

```python
# Historical daily bars (not currently used by FinAlly, documented for completeness)
aggs = list(client.list_aggs(
    ticker="AAPL",
    multiplier=1,
    timespan="day",
    from_="2026-01-01",
    to="2026-06-30",
    limit=50000,
))
```

The client is **synchronous** (blocking HTTP calls under the hood). In an
asyncio app like FinAlly's FastAPI backend, calls must be wrapped in
`asyncio.to_thread(...)` to avoid blocking the event loop — this is exactly
what `backend/app/market/massive_client.py` already does.

Pagination: `list_*` methods paginate automatically by default
(`pagination=True`); `limit` controls page size, not total result count. The
`get_snapshot_all` call used here returns a single non-paginated list.

## Error Modes to Handle

| Condition | Behavior |
|---|---|
| Invalid/revoked API key | HTTP 401 |
| Rate limit exceeded | HTTP 429 |
| Unknown/delisted ticker in `tickers` list | Simply absent from the response array — no per-ticker error |
| Network/timeout | Client raises a connection error |

Per `planning/PLAN.md` §5, FinAlly does **not** fall back to the simulator on
any of these — it logs the failure and retries on the next poll interval,
leaving the price cache stale for affected tickers until a poll succeeds.

## Sources

- [API Docs | Massive](https://massive.com/docs)
- [Overview | Stocks REST API - Massive](https://massive.com/docs/rest/stocks/overview)
- [Full Market Snapshot | Stocks REST API - Massive](https://massive.com/docs/rest/stocks/snapshots/full-market-snapshot)
- [Previous Day Bar (OHLC) | Stocks REST API - Massive](https://massive.com/docs/rest/stocks/aggregates/previous-day-bar)
- [Daily Market Summary (OHLC) | Stocks REST API - Massive](https://massive.com/docs/rest/stocks/aggregates/daily-market-summary)
- [GitHub - massive-com/client-python](https://github.com/massive-com/client-python)
- [What is the request limit for Massive's RESTful APIs?](https://polygon.io/knowledge-base/article/what-is-the-request-limit-for-polygons-restful-apis)
