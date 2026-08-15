# Market Data Backend — Detailed Design

**Status of this document:** the market data subsystem it describes is
**already built and merged** at `backend/app/market/` (see
`planning/MARKET_DATA_SUMMARY.md` for the delivery summary). This is a
single, consolidated design reference — architecture, full code, and
integration guidance in one place — pulled directly from the real source so
it can be trusted as accurate. The three focused docs (`MARKET_INTERFACE.md`,
`MARKET_SIMULATOR.md`, `MASSIVE_API.md`) remain the per-topic references;
this document exists to walk through the *whole* subsystem end-to-end,
including the integration points (`main.py`, watchlist, trades) that
**do not exist yet** — the rest of the backend is still to be built, per
`planning/PLAN.md`.

An earlier version of this document (`planning/archive/MARKET_DATA_DESIGN.md`)
was the pre-implementation plan. It's superseded by this one in a few places
where the shipped code diverged from the plan during a code review pass (see
`planning/archive/MARKET_DATA_REVIEW.md`) — notably: no lazy imports for
`massive` (it's a core dependency), `GBMSimulator` gained a public
`get_tickers()`, the unused `DEFAULT_CORR` constant was removed, and the SSE
generator's return type was fixed. Everything below reflects what's actually
in the repo today, plus one still-open bug (§8.4) that the review flagged and
that has not been fixed.

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [File Structure](#2-file-structure)
3. [Data Model — `PriceUpdate`](#3-data-model--priceupdate)
4. [`PriceCache` — The Shared Point of Truth](#4-pricecache--the-shared-point-of-truth)
5. [`MarketDataSource` — The Producer Contract](#5-marketdatasource--the-producer-contract)
6. [Seed Prices & Ticker Parameters](#6-seed-prices--ticker-parameters)
7. [The GBM Simulator](#7-the-gbm-simulator)
8. [The Massive API Client](#8-the-massive-api-client)
9. [`create_market_data_source()` — The Factory](#9-create_market_data_source--the-factory)
10. [SSE Streaming Endpoint](#10-sse-streaming-endpoint)
11. [Wiring Into FastAPI (Not Yet Built)](#11-wiring-into-fastapi-not-yet-built)
12. [Watchlist Coordination (Not Yet Built)](#12-watchlist-coordination-not-yet-built)
13. [Testing Strategy](#13-testing-strategy)
14. [Known Issues](#14-known-issues)
15. [Configuration Summary](#15-configuration-summary)
16. [Extension Points](#16-extension-points)

---

## 1. Architecture Overview

```
                 MarketDataSource (ABC)
                 ├── SimulatorDataSource   (GBM, in-process, no API key)
                 └── MassiveDataSource     (Polygon.io REST poller)
                            │
                            │  writes via PriceCache.update()
                            ▼
                       PriceCache
                 (thread-safe, in-memory, single instance)
                            │
                            │  reads via .get() / .get_all() / .version
              ┌─────────────┼──────────────────┐
              ▼             ▼                  ▼
     SSE /api/stream/   Portfolio           Trade
        prices          valuation          execution
   (not yet built)    (not yet built)    (not yet built)
```

Design goals (unpacked from `planning/PLAN.md` §6 and
`MARKET_INTERFACE.md`):

1. **Source-agnostic downstream code.** Nothing outside `app/market/`
   imports `SimulatorDataSource` or `MassiveDataSource` by name — only
   `PriceCache` and the `MarketDataSource` ABC.
2. **One shared mutable point of truth.** `PriceCache` decouples production
   rate (500ms for the simulator, 15s for Massive) from consumption rate
   (SSE polls the cache every 500ms regardless of source).
3. **Dynamic ticker set.** `add_ticker`/`remove_ticker` work at runtime, no
   restart, because the watchlist changes via user action or AI chat.
4. **Fail stale, not silent-fallback.** A failed Massive poll never falls
   back to the simulator — see §8.3 and §14.

---

## 2. File Structure

```
backend/app/market/
├── __init__.py         — public exports
├── models.py            — PriceUpdate
├── cache.py              — PriceCache
├── interface.py           — MarketDataSource (ABC)
├── seed_prices.py          — SEED_PRICES, TICKER_PARAMS, correlation constants
├── simulator.py             — GBMSimulator + SimulatorDataSource
├── massive_client.py         — MassiveDataSource
├── factory.py                 — create_market_data_source()
└── stream.py                   — create_stream_router() (SSE endpoint)

backend/tests/market/
├── test_models.py, test_cache.py, test_simulator.py,
├── test_simulator_source.py, test_factory.py, test_massive.py

backend/market_data_demo.py   — Rich terminal demo, `uv run market_data_demo.py`
```

`__init__.py` re-exports everything downstream code needs:

```python
from .cache import PriceCache
from .factory import create_market_data_source
from .interface import MarketDataSource
from .models import PriceUpdate
from .stream import create_stream_router

__all__ = [
    "PriceUpdate",
    "PriceCache",
    "MarketDataSource",
    "create_market_data_source",
    "create_stream_router",
]
```

So the rest of the backend only ever needs:

```python
from app.market import PriceCache, PriceUpdate, MarketDataSource, create_market_data_source, create_stream_router
```

---

## 3. Data Model — `PriceUpdate`

`backend/app/market/models.py`

```python
@dataclass(frozen=True, slots=True)
class PriceUpdate:
    """Immutable snapshot of a single ticker's price at a point in time."""

    ticker: str
    price: float
    previous_price: float
    timestamp: float = field(default_factory=time.time)  # Unix seconds

    @property
    def change(self) -> float:
        """Absolute price change from previous update."""
        return round(self.price - self.previous_price, 4)

    @property
    def change_percent(self) -> float:
        """Percentage change from previous update."""
        if self.previous_price == 0:
            return 0.0
        return round((self.price - self.previous_price) / self.previous_price * 100, 4)

    @property
    def direction(self) -> str:
        """'up', 'down', or 'flat'."""
        if self.price > self.previous_price:
            return "up"
        elif self.price < self.previous_price:
            return "down"
        return "flat"

    def to_dict(self) -> dict:
        """Serialize for JSON / SSE transmission."""
        return {
            "ticker": self.ticker,
            "price": self.price,
            "previous_price": self.previous_price,
            "timestamp": self.timestamp,
            "change": self.change,
            "change_percent": self.change_percent,
            "direction": self.direction,
        }
```

Design notes:

- `frozen=True, slots=True` — immutable (safe to hand to an SSE consumer
  mid-serialization without a mutation race) and memory-efficient (no
  per-instance `__dict__`).
- `timestamp` is **always Unix seconds** internally. Massive's raw API
  returns nanoseconds — the client (§8) must convert before calling
  `PriceCache.update()`.
- `to_dict()` is the only serialization path used by the SSE endpoint — one
  format, one place it's defined.
- `change_percent` guards against division by zero for a ticker whose
  previous price was `0` (shouldn't happen with real seed data, but cheap
  insurance against a `ZeroDivisionError` taking down the SSE loop).

---

## 4. `PriceCache` — The Shared Point of Truth

`backend/app/market/cache.py`

```python
class PriceCache:
    """Thread-safe in-memory cache of the latest price for each ticker.

    Writers: SimulatorDataSource or MassiveDataSource (one at a time).
    Readers: SSE streaming endpoint, portfolio valuation, trade execution.
    """

    def __init__(self) -> None:
        self._prices: dict[str, PriceUpdate] = {}
        self._lock = Lock()
        self._version: int = 0  # Monotonically increasing; bumped on every update

    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
        with self._lock:
            ts = timestamp or time.time()
            prev = self._prices.get(ticker)
            previous_price = prev.price if prev else price

            update = PriceUpdate(
                ticker=ticker,
                price=round(price, 2),
                previous_price=round(previous_price, 2),
                timestamp=ts,
            )
            self._prices[ticker] = update
            self._version += 1
            return update

    def get(self, ticker: str) -> PriceUpdate | None:
        with self._lock:
            return self._prices.get(ticker)

    def get_all(self) -> dict[str, PriceUpdate]:
        with self._lock:
            return dict(self._prices)

    def get_price(self, ticker: str) -> float | None:
        update = self.get(ticker)
        return update.price if update else None

    def remove(self, ticker: str) -> None:
        with self._lock:
            self._prices.pop(ticker, None)

    @property
    def version(self) -> int:
        return self._version

    def __len__(self) -> int:
        with self._lock:
            return len(self._prices)

    def __contains__(self, ticker: str) -> bool:
        with self._lock:
            return ticker in self._prices
```

**Why a `Lock`, not an `asyncio.Lock`.** `MassiveDataSource` runs its HTTP
call via `asyncio.to_thread(...)` (§8), so the write to `PriceCache.update()`
can happen from a worker thread, not the event loop. A plain `threading.Lock`
is correct here; an `asyncio.Lock` would not protect against that
cross-thread write.

**Why `update()` — not a raw setter.** Callers never construct a
`PriceUpdate` directly. `update()` is the single write path so that
`previous_price` derivation, rounding, and `direction`/`change` computation
happen in exactly one place. On a ticker's very first write, `previous_price`
is set equal to `price` — this gives `direction == "flat"` on the initial
tick instead of a spurious green/red flash when a client first connects.

**Why `version`, not a pub/sub or diff.** The SSE loop (§10) needs to answer
"did anything change since I last sent a frame?" cheaply, every 500ms,
without diffing two dictionaries. A single incrementing `int` answers that
in O(1). On CPython, a single `int` read/write is GIL-atomic, so the
`version` property is safe to read without the lock even though it doesn't
explicitly take one (see §14 for the theoretical no-GIL-build caveat).

---

## 5. `MarketDataSource` — The Producer Contract

`backend/app/market/interface.py`

```python
class MarketDataSource(ABC):
    """Contract for market data providers.

    Implementations push price updates into a shared PriceCache on their own
    schedule. Downstream code never calls the data source directly for prices —
    it reads from the cache.
    """

    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Begin producing price updates for the given tickers.

        Starts a background task. Must be called exactly once."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the background task. Safe to call multiple times."""

    @abstractmethod
    async def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the active set. No-op if already present."""

    @abstractmethod
    async def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker. Also removes it from the PriceCache."""

    @abstractmethod
    def get_tickers(self) -> list[str]:
        """Return the current list of actively tracked tickers."""
```

Lifecycle both implementations follow:

```python
source = create_market_data_source(cache)
await source.start(["AAPL", "GOOGL", ...])   # exactly once
await source.add_ticker("TSLA")               # any time after start()
await source.remove_ticker("GOOGL")           # any time after start()
await source.stop()                           # idempotent
```

Neither implementation *returns* prices to a caller — they only write into
the injected `PriceCache`. That's the whole strategy pattern: `stream.py`,
and eventually the portfolio/trade code, only ever hold a `PriceCache`
reference, never a `SimulatorDataSource` or `MassiveDataSource` reference.

---

## 6. Seed Prices & Ticker Parameters

`backend/app/market/seed_prices.py`

```python
SEED_PRICES: dict[str, float] = {
    "AAPL": 190.00, "GOOGL": 175.00, "MSFT": 420.00, "AMZN": 185.00,
    "TSLA": 250.00, "NVDA": 800.00, "META": 500.00, "JPM": 195.00,
    "V": 280.00, "NFLX": 600.00,
}

TICKER_PARAMS: dict[str, dict[str, float]] = {
    "AAPL": {"sigma": 0.22, "mu": 0.05},
    "GOOGL": {"sigma": 0.25, "mu": 0.05},
    "MSFT": {"sigma": 0.20, "mu": 0.05},
    "AMZN": {"sigma": 0.28, "mu": 0.05},
    "TSLA": {"sigma": 0.50, "mu": 0.03},   # High volatility
    "NVDA": {"sigma": 0.40, "mu": 0.08},   # High volatility, strong drift
    "META": {"sigma": 0.30, "mu": 0.05},
    "JPM": {"sigma": 0.18, "mu": 0.04},    # Low volatility (bank)
    "V": {"sigma": 0.17, "mu": 0.04},      # Low volatility (payments)
    "NFLX": {"sigma": 0.35, "mu": 0.05},
}

DEFAULT_PARAMS: dict[str, float] = {"sigma": 0.25, "mu": 0.05}

CORRELATION_GROUPS: dict[str, set[str]] = {
    "tech": {"AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "NFLX"},
    "finance": {"JPM", "V"},
}

INTRA_TECH_CORR = 0.6      # Tech stocks move together
INTRA_FINANCE_CORR = 0.5   # Finance stocks move together
CROSS_GROUP_CORR = 0.3     # Between sectors / unknown tickers
TSLA_CORR = 0.3            # TSLA does its own thing
```

Any ticker string not in `SEED_PRICES`/`TICKER_PARAMS` (per `PLAN.md` §6,
**any** symbol can be added to the watchlist) falls back to a random seed
price in `[50, 300]` and `DEFAULT_PARAMS` — this happens in
`GBMSimulator._add_ticker_internal` (§7.1), not in this module; this module
only holds the static lookup tables.

---

## 7. The GBM Simulator

Default data source (used whenever `MASSIVE_API_KEY` is unset). Fully
in-process, no external dependencies, so the app works offline / without an
API key. Full math rationale is in `planning/MARKET_SIMULATOR.md`; this
section gives the complete, current code.

### 7.1 `GBMSimulator` — pure math, no asyncio

`backend/app/market/simulator.py`

```python
class GBMSimulator:
    """Geometric Brownian Motion simulator for correlated stock prices.

    Math:
        S(t+dt) = S(t) * exp((mu - sigma^2/2) * dt + sigma * sqrt(dt) * Z)
    """

    # 252 trading days * 6.5 hours/day * 3600 seconds/hour = 5,896,800 seconds
    TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600
    DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR  # ~8.48e-8, for 500ms ticks

    def __init__(self, tickers: list[str], dt: float = DEFAULT_DT,
                 event_probability: float = 0.001) -> None:
        self._dt = dt
        self._event_prob = event_probability
        self._tickers: list[str] = []
        self._prices: dict[str, float] = {}
        self._params: dict[str, dict[str, float]] = {}
        self._cholesky: np.ndarray | None = None

        for ticker in tickers:
            self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    def step(self) -> dict[str, float]:
        """Advance all tickers by one time step. Hot path — runs every 500ms."""
        n = len(self._tickers)
        if n == 0:
            return {}

        z_independent = np.random.standard_normal(n)
        z_correlated = self._cholesky @ z_independent if self._cholesky is not None else z_independent

        result: dict[str, float] = {}
        for i, ticker in enumerate(self._tickers):
            params = self._params[ticker]
            mu, sigma = params["mu"], params["sigma"]

            drift = (mu - 0.5 * sigma**2) * self._dt
            diffusion = sigma * math.sqrt(self._dt) * z_correlated[i]
            self._prices[ticker] *= math.exp(drift + diffusion)

            # ~0.1% chance per tick per ticker of a 2-5% shock, for visual drama
            if random.random() < self._event_prob:
                shock_magnitude = random.uniform(0.02, 0.05)
                shock_sign = random.choice([-1, 1])
                self._prices[ticker] *= 1 + shock_magnitude * shock_sign

            result[ticker] = round(self._prices[ticker], 2)

        return result

    def add_ticker(self, ticker: str) -> None:
        if ticker in self._prices:
            return
        self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    def remove_ticker(self, ticker: str) -> None:
        if ticker not in self._prices:
            return
        self._tickers.remove(ticker)
        del self._prices[ticker]
        del self._params[ticker]
        self._rebuild_cholesky()

    def get_price(self, ticker: str) -> float | None:
        return self._prices.get(ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    def _add_ticker_internal(self, ticker: str) -> None:
        if ticker in self._prices:
            return
        self._tickers.append(ticker)
        self._prices[ticker] = SEED_PRICES.get(ticker, random.uniform(50.0, 300.0))
        self._params[ticker] = TICKER_PARAMS.get(ticker, dict(DEFAULT_PARAMS))

    def _rebuild_cholesky(self) -> None:
        """O(n^2), cheap for n < 50. Called on every add_ticker/remove_ticker."""
        n = len(self._tickers)
        if n <= 1:
            self._cholesky = None
            return

        corr = np.eye(n)
        for i in range(n):
            for j in range(i + 1, n):
                rho = self._pairwise_correlation(self._tickers[i], self._tickers[j])
                corr[i, j] = corr[j, i] = rho

        self._cholesky = np.linalg.cholesky(corr)

    @staticmethod
    def _pairwise_correlation(t1: str, t2: str) -> float:
        tech, finance = CORRELATION_GROUPS["tech"], CORRELATION_GROUPS["finance"]
        if t1 == "TSLA" or t2 == "TSLA":
            return TSLA_CORR
        if t1 in tech and t2 in tech:
            return INTRA_TECH_CORR
        if t1 in finance and t2 in finance:
            return INTRA_FINANCE_CORR
        return CROSS_GROUP_CORR
```

Internal state is three parallel structures keyed by ticker (`_prices`,
`_params`) plus an ordered `_tickers` list. List order is load-bearing: it's
the index basis for the Cholesky matrix and the correlated-draw vector, so
`_tickers` and the matrix must stay in lockstep — which is why every mutation
of `_tickers` immediately calls `_rebuild_cholesky()`.

### 7.2 `SimulatorDataSource` — the async `MarketDataSource` adapter

```python
class SimulatorDataSource(MarketDataSource):
    """Runs a background asyncio task that steps the GBM sim every
    `update_interval` seconds and writes results to the PriceCache."""

    def __init__(self, price_cache: PriceCache, update_interval: float = 0.5,
                 event_probability: float = 0.001) -> None:
        self._cache = price_cache
        self._interval = update_interval
        self._event_prob = event_probability
        self._sim: GBMSimulator | None = None
        self._task: asyncio.Task | None = None

    async def start(self, tickers: list[str]) -> None:
        self._sim = GBMSimulator(tickers=tickers, event_probability=self._event_prob)
        # Seed the cache synchronously so SSE has data on the very first frame
        for ticker in tickers:
            price = self._sim.get_price(ticker)
            if price is not None:
                self._cache.update(ticker=ticker, price=price)
        self._task = asyncio.create_task(self._run_loop(), name="simulator-loop")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def add_ticker(self, ticker: str) -> None:
        if self._sim:
            self._sim.add_ticker(ticker)
            price = self._sim.get_price(ticker)
            if price is not None:
                self._cache.update(ticker=ticker, price=price)

    async def remove_ticker(self, ticker: str) -> None:
        if self._sim:
            self._sim.remove_ticker(ticker)
        self._cache.remove(ticker)

    def get_tickers(self) -> list[str]:
        return self._sim.get_tickers() if self._sim else []

    async def _run_loop(self) -> None:
        while True:
            try:
                if self._sim:
                    prices = self._sim.step()
                    for ticker, price in prices.items():
                        self._cache.update(ticker=ticker, price=price)
            except Exception:
                logger.exception("Simulator step failed")
            await asyncio.sleep(self._interval)
```

`_run_loop` wraps each step in `try/except Exception` so a single bad tick
(e.g., a numpy edge case) is logged and the loop keeps running rather than
silently dying — this is the only background task keeping the entire
watchlist's prices alive, so it must never crash on a transient error.

`GBMSimulator` owns zero asyncio state deliberately — it's kept pure Python
+ numpy so its math is unit-testable without an event loop (§13.1); the
async adapter owns only task lifecycle and the translation from
`{ticker: price}` to `PriceCache.update()` calls.

---

## 8. The Massive API Client

`backend/app/market/massive_client.py`. Full API research (endpoints, rate
limits, response shapes, official client) is in `planning/MASSIVE_API.md`;
this section is the implementation.

### 8.1 Full code

```python
from massive import RESTClient
from massive.rest.models import SnapshotMarketType


class MassiveDataSource(MarketDataSource):
    """Polls GET /v2/snapshot/locale/us/markets/stocks/tickers for all
    watched tickers in a single API call, then writes results to the
    PriceCache.

    Rate limits: free tier 5 req/min -> poll every 15s (default);
    paid tiers -> poll every 2-5s (pass a smaller poll_interval).
    """

    def __init__(self, api_key: str, price_cache: PriceCache,
                 poll_interval: float = 15.0) -> None:
        self._api_key = api_key
        self._cache = price_cache
        self._interval = poll_interval
        self._tickers: list[str] = []
        self._task: asyncio.Task | None = None
        self._client: RESTClient | None = None

    async def start(self, tickers: list[str]) -> None:
        self._client = RESTClient(api_key=self._api_key)
        self._tickers = list(tickers)
        await self._poll_once()   # immediate first poll — cache has data right away
        self._task = asyncio.create_task(self._poll_loop(), name="massive-poller")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._client = None

    async def add_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        if ticker not in self._tickers:
            self._tickers.append(ticker)
            # No cache write here — the ticker appears on the next scheduled poll

    async def remove_ticker(self, ticker: str) -> None:
        ticker = ticker.upper().strip()
        self._tickers = [t for t in self._tickers if t != ticker]
        self._cache.remove(ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            await self._poll_once()

    async def _poll_once(self) -> None:
        if not self._tickers or not self._client:
            return
        try:
            # RESTClient is synchronous — run in a thread to avoid blocking the event loop
            snapshots = await asyncio.to_thread(self._fetch_snapshots)
        except Exception as e:
            logger.error("Massive poll failed: %s", e)
            # Deliberately not re-raised — the loop retries next interval
            return

        processed = 0
        for snap in snapshots or []:
            ticker = normalize_ticker(getattr(snap, "ticker", "") or "")
            if not ticker:
                continue
            price = _extract_price(snap)          # last trade → day close → prev close
            if price is None:
                logger.warning("Skipping snapshot for %s: no usable price", ticker)
                continue
            # sip_timestamp is Unix nanoseconds; None → cache stamps wall-clock time
            self._cache.update(ticker=ticker, price=price, timestamp=_extract_timestamp(snap))
            processed += 1

    def _fetch_snapshots(self) -> list:
        return self._client.get_snapshot_all(
            market_type=SnapshotMarketType.STOCKS,
            tickers=self._tickers,
        )
```

### 8.2 Why `asyncio.to_thread`

The official `massive` Python client is synchronous (blocking HTTP under the
hood). FastAPI's event loop must not block on that call, so `_fetch_snapshots`
— the one method that actually talks to the network — is the only piece
wrapped in `asyncio.to_thread(...)`. Everything else in `_poll_once` (parsing,
cache writes) runs back on the event loop after `to_thread` returns.

### 8.3 Error handling philosophy

Per `planning/PLAN.md` §5, a failed poll must **never** fall back to the
simulator. `_poll_once` reflects that exactly:

| Failure | Handling |
|---|---|
| Invalid/revoked key (401) | Caught by the outer `except Exception`, logged, retried next interval |
| Rate limited (429) | Same |
| Network/timeout error | Same |
| One ticker missing/malformed in the response | Caught per-snapshot by the inner `except (AttributeError, TypeError)`, that ticker is skipped, the rest of the batch still processes |

The cache simply goes stale for affected tickers — the SSE connection to the
browser stays up throughout (§10); it just keeps serving the last good price
until a poll succeeds again.

### 8.4 `add_ticker` latency differs from the simulator

Note the comment in `add_ticker` above: unlike `SimulatorDataSource`, which
seeds the cache **synchronously** the moment a ticker is added,
`MassiveDataSource.add_ticker` only appends to `self._tickers` — the ticker
has no price in the cache until the next scheduled poll (up to 15s later on
free tier). Any UI/API code reading the cache for a freshly-added ticker must
tolerate `PriceCache.get()` returning `None` for a few seconds under Massive
mode, whereas under simulator mode it never does.

---

## 9. `create_market_data_source()` — The Factory

`backend/app/market/factory.py`

```python
def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    """- MASSIVE_API_KEY set and non-empty -> MassiveDataSource
       - Otherwise -> SimulatorDataSource
       Returns an unstarted source. Caller must await source.start(tickers)."""
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()

    if api_key:
        logger.info("Market data source: Massive API (real data)")
        return MassiveDataSource(api_key=api_key, price_cache=price_cache)
    else:
        logger.info("Market data source: GBM Simulator")
        return SimulatorDataSource(price_cache=price_cache)
```

This is the **only** place `MASSIVE_API_KEY` is read for source selection.
Nothing else — not `main.py`, not tests, not the frontend — branches on that
env var directly.

---

## 10. SSE Streaming Endpoint

`backend/app/market/stream.py`

```python
router = APIRouter(prefix="/api/stream", tags=["streaming"])


def create_stream_router(price_cache: PriceCache) -> APIRouter:
    """Factory pattern lets us inject the PriceCache without globals."""

    @router.get("/prices")
    async def stream_prices(request: Request) -> StreamingResponse:
        return StreamingResponse(
            _generate_events(price_cache, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # disable nginx buffering if proxied
            },
        )

    return router


async def _generate_events(price_cache: PriceCache, request: Request,
                            interval: float = 0.5) -> AsyncGenerator[str, None]:
    yield "retry: 1000\n\n"   # browser auto-reconnects 1s after a drop

    last_version = -1
    try:
        while True:
            if await request.is_disconnected():
                break

            current_version = price_cache.version
            if current_version != last_version:
                last_version = current_version
                prices = price_cache.get_all()
                if prices:
                    data = {ticker: update.to_dict() for ticker, update in prices.items()}
                    yield f"data: {json.dumps(data)}\n\n"

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        pass
```

### Wire format

```
retry: 1000

data: {"AAPL": {"ticker": "AAPL", "price": 190.5, "previous_price": 190.42, "timestamp": 1755248901.2, "change": 0.08, "change_percent": 0.042, "direction": "up"}, "GOOGL": {...}, ...}

```
(each frame is the **full current snapshot** of every tracked ticker — not a
diff/delta of just what changed)

### Why poll-and-push instead of event-driven

`_generate_events` polls `price_cache.version` every `interval` seconds
rather than the cache notifying it — this is deliberately simple: no
pub/sub, no per-client subscriber list, no risk of a slow consumer blocking
a producer. The tradeoff is up to `interval` (500ms) of added latency
between a price update and a client seeing it, which is invisible at this
tick rate. `X-Accel-Buffering: no` matters if this is ever deployed behind
nginx — otherwise nginx buffers the stream and defeats the whole point of
SSE.

---

## 11. Wiring Into FastAPI (Not Yet Built)

There is no `backend/app/main.py` yet — the market data subsystem is
complete but unwired, since the rest of the backend (DB, portfolio,
watchlist, chat) hasn't been built. This section is forward-looking
guidance for whoever builds `main.py`, consistent with `planning/PLAN.md`
§7 (DB schema init happens *before* background tasks start).

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.market import PriceCache, create_market_data_source, create_stream_router
from app.db import init_db, get_watchlist  # not yet built


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Schema init + seed (strictly before anything reads the DB)
    init_db()

    # 2. Build the shared cache and source, seeded from the persisted watchlist
    price_cache = PriceCache()
    market_source = create_market_data_source(price_cache)
    tickers = get_watchlist()  # e.g. the 10 default tickers on a fresh DB
    await market_source.start(tickers)

    app.state.price_cache = price_cache
    app.state.market_source = market_source

    yield  # app runs

    # 3. Shutdown: stop the background task cleanly
    await market_source.stop()


app = FastAPI(lifespan=lifespan)
app.include_router(create_stream_router(app.state.price_cache))
```

`app.state` is the simplest way to make `price_cache` and `market_source`
reachable from route handlers without a global. A FastAPI dependency can
wrap that for cleaner handler signatures:

```python
from fastapi import Request


def get_price_cache(request: Request) -> PriceCache:
    return request.app.state.price_cache


def get_market_source(request: Request) -> MarketDataSource:
    return request.app.state.market_source
```

```python
from fastapi import Depends

@router.get("/api/portfolio")
async def get_portfolio(cache: PriceCache = Depends(get_price_cache)):
    positions = load_positions()  # not yet built
    for pos in positions:
        current_price = cache.get_price(pos.ticker)  # None if not (yet) cached
        ...
```

`create_stream_router(price_cache)` must be called with the *same*
`PriceCache` instance passed to `create_market_data_source` — there is
exactly one `PriceCache` for the whole app; passing a second instance
anywhere silently splits reads from writes.

---

## 12. Watchlist Coordination (Not Yet Built)

The watchlist lives in the `watchlist` SQLite table (`planning/PLAN.md`
§7); `market_source` is the in-memory mirror of that table's ticker column.
Every mutation to the table must be paired with the matching
`market_source` call so the two never drift apart:

### Adding a ticker

```python
@router.post("/api/watchlist")
async def add_to_watchlist(body: AddTickerRequest,
                            source: MarketDataSource = Depends(get_market_source)):
    ticker = body.ticker.upper().strip()
    if ticker_already_watched(ticker):        # not yet built
        raise HTTPException(409, detail=f"{ticker} is already on the watchlist")

    insert_watchlist_row(ticker)               # DB write, not yet built
    await source.add_ticker(ticker)             # in-memory mirror
    return {"ticker": ticker}
```

DB write before the in-memory call: if the DB insert fails (e.g., a race on
the UNIQUE constraint), `source.add_ticker` never runs and the two stay
consistent. `add_ticker` is a no-op if the ticker's already tracked (§5), so
even a partial-failure retry is safe.

### Removing a ticker

```python
@router.delete("/api/watchlist/{ticker}")
async def remove_from_watchlist(ticker: str,
                                 source: MarketDataSource = Depends(get_market_source)):
    ticker = ticker.upper().strip()
    if not ticker_currently_watched(ticker):    # not yet built
        raise HTTPException(404, detail=f"{ticker} is not on the watchlist")

    delete_watchlist_row(ticker)                 # DB write
    await source.remove_ticker(ticker)            # also clears PriceCache (§5, §7.2, §8.1)
    return {"ticker": ticker}
```

### Edge case: removing a ticker with an open position

`PLAN.md` doesn't forbid removing a watched ticker the user still holds
shares in — the `positions` table is independent of `watchlist`. If that
happens, `PriceCache.remove()` drops the last known price, so portfolio
valuation code (§11) must handle `cache.get_price(ticker) is None` for a
held position — e.g., by falling back to `avg_cost` or the last snapshot
value rather than crashing. This is a portfolio-module concern, not a
market-data one; flagged here because it's a direct consequence of how
`remove_ticker` behaves.

---

## 13. Testing Strategy

**Current: 73 tests across 6 modules, 84% overall coverage** (per
`planning/MARKET_DATA_SUMMARY.md`). The split below is what makes that
coverage achievable without needing an event loop or a live API for most of
it.

### 13.1 `GBMSimulator` — pure math, no asyncio (`test_simulator.py`, 17 tests, 98%)

Because `GBMSimulator.step()` has no `await` in it, tests can seed
`numpy.random`/`random` and assert deterministically:

```python
def test_step_moves_price_and_preserves_positivity():
    sim = GBMSimulator(tickers=["AAPL"])
    start = sim.get_price("AAPL")
    for _ in range(1000):
        sim.step()
    assert sim.get_price("AAPL") > 0   # GBM guarantees this by construction

def test_add_ticker_rebuilds_cholesky_without_error():
    sim = GBMSimulator(tickers=["AAPL", "GOOGL"])
    sim.add_ticker("UNKNOWNTICKER")     # exercises the random-seed fallback path
    assert "UNKNOWNTICKER" in sim.get_tickers()
    sim.step()   # would raise if the Cholesky matrix and ticker list desynced

def test_pairwise_correlation_tsla_is_independent():
    assert GBMSimulator._pairwise_correlation("TSLA", "AAPL") == TSLA_CORR
    assert GBMSimulator._pairwise_correlation("AAPL", "GOOGL") == INTRA_TECH_CORR
```

### 13.2 `PriceCache` — thread safety and versioning (`test_cache.py`, 13 tests, 100%)

```python
def test_first_update_has_flat_direction():
    cache = PriceCache()
    update = cache.update("AAPL", 190.0)
    assert update.direction == "flat"
    assert update.previous_price == update.price

def test_version_increments_on_every_update():
    cache = PriceCache()
    v0 = cache.version
    cache.update("AAPL", 190.0)
    assert cache.version == v0 + 1

def test_remove_drops_ticker():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    cache.remove("AAPL")
    assert cache.get("AAPL") is None
```

### 13.3 `SimulatorDataSource` — async integration against a real `PriceCache` (`test_simulator_source.py`, 10 tests)

```python
@pytest.mark.asyncio
async def test_start_seeds_cache_before_loop_runs():
    cache = PriceCache()
    source = SimulatorDataSource(cache, update_interval=10.0)  # slow, so the loop doesn't tick during the test
    await source.start(["AAPL"])
    assert cache.get_price("AAPL") is not None   # seeded synchronously in start()
    await source.stop()

@pytest.mark.asyncio
async def test_stop_is_idempotent():
    cache = PriceCache()
    source = SimulatorDataSource(cache)
    await source.start(["AAPL"])
    await source.stop()
    await source.stop()   # must not raise
```

### 13.4 `MassiveDataSource` — mocked REST calls (`test_massive.py`, 13 tests, 56% — API methods mocked)

```python
@pytest.mark.asyncio
async def test_poll_updates_cache(monkeypatch):
    cache = PriceCache()
    source = MassiveDataSource(api_key="fake", price_cache=cache, poll_interval=100.0)
    source._client = object()  # bypass RESTClient construction

    fake_snapshot = SimpleNamespace(
        ticker="AAPL",
        last_trade=SimpleNamespace(price=190.5, timestamp=1_700_000_000_000),
    )
    monkeypatch.setattr(source, "_fetch_snapshots", lambda: [fake_snapshot])

    source._tickers = ["AAPL"]
    await source._poll_once()

    assert cache.get_price("AAPL") == 190.5

@pytest.mark.asyncio
async def test_malformed_snapshot_is_skipped_not_fatal(monkeypatch):
    cache = PriceCache()
    source = MassiveDataSource(api_key="fake", price_cache=cache)
    source._client = object()
    source._tickers = ["AAPL", "GOOGL"]

    bad = SimpleNamespace(ticker="AAPL", last_trade=None)   # AttributeError on .price
    good = SimpleNamespace(ticker="GOOGL", last_trade=SimpleNamespace(price=175.0, timestamp=1_700_000_000_000))
    monkeypatch.setattr(source, "_fetch_snapshots", lambda: [bad, good])

    await source._poll_once()

    assert cache.get_price("AAPL") is None      # skipped
    assert cache.get_price("GOOGL") == 175.0     # still processed
```

Note per `planning/archive/MARKET_DATA_REVIEW.md`: these tests require the
`massive` package importable (it's a core dependency in `pyproject.toml`,
not lazily imported — see the top-of-document note on where this design
diverged from the original plan), and patch/monkeypatch targets that
reference the module attribute directly rather than a name that only exists
inside a function scope.

### 13.5 `create_market_data_source` — factory selection (`test_factory.py`, 7 tests, 100%)

```python
def test_factory_returns_simulator_when_no_key(monkeypatch):
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    source = create_market_data_source(PriceCache())
    assert isinstance(source, SimulatorDataSource)

def test_factory_returns_massive_when_key_set(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "test-key")
    source = create_market_data_source(PriceCache())
    assert isinstance(source, MassiveDataSource)

def test_factory_treats_whitespace_only_key_as_unset(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "   ")
    source = create_market_data_source(PriceCache())
    assert isinstance(source, SimulatorDataSource)
```

### 13.6 SSE streaming — the known coverage gap (`stream.py`, 31% coverage)

No dedicated tests exist today; `_generate_events` needs a running ASGI
context to exercise properly. When the rest of the backend is built and a
`TestClient`/`httpx.AsyncClient` fixture exists, a minimal integration test
looks like:

```python
@pytest.mark.asyncio
async def test_sse_stream_emits_seeded_prices(async_client, price_cache):
    price_cache.update("AAPL", 190.0)
    async with async_client.stream("GET", "/api/stream/prices") as response:
        line = await anext(response.aiter_lines())
        assert line.startswith("retry:")
        # next non-empty line should be a `data:` frame containing AAPL
```

---

## 14. Known Issues

All three issues previously recorded here have been **resolved**. They are
kept below with their fixes for the record.

### 14.1 Massive timestamp field — cache never populated with a real key (RESOLVED)

`MassiveDataSource._poll_once` (§8.1) used to do:

```python
timestamp = snap.last_trade.timestamp / 1000.0
```

The installed `massive` client's `LastTrade` model has **no `.timestamp`
attribute** — the JSON field `t` (Unix **nanoseconds**) is exposed as
`.sip_timestamp`. Accessing `.timestamp` raised `AttributeError`, which was
caught by the per-snapshot `except (AttributeError, TypeError)` in
`_poll_once` and logged as a warning (`"Skipping snapshot for %s: %s"`). The
practical effect: **with a real `MASSIVE_API_KEY` set, every poll skipped
every ticker, and the price cache was never populated.** The simulator path
was entirely unaffected.

**Fixed** by extracting price and timestamp through dedicated helpers
(`_extract_price` / `_extract_timestamp`) that read `sip_timestamp` and
divide by `1e9`. Two things made this bug survive the original test suite,
and both were addressed:

- The tests built snapshots out of bare `MagicMock`, which fabricates any
  attribute asked of it — so `mock.last_trade.timestamp` answered happily
  while the real model would not. `test_massive.py` now uses plain fake
  classes mirroring the real models, so a wrong attribute name fails loudly.
- The per-snapshot `except (AttributeError, TypeError)` turned a hard coding
  error into a routine warning. Extraction is now explicit `getattr`-based
  with validation, so "no usable price" is a real data condition rather than
  a swallowed typo.

The fix also made the poller more tolerant of the sparse-snapshot cases
`MASSIVE_API.md` warns about: a snapshot with no `lastTrade` (pre-market, or
a symbol that hasn't traded yet today) now falls back to `day.close` and then
`prev_day.close`, and a missing timestamp no longer discards an otherwise
good price — `PriceCache` stamps it with wall-clock time instead.

### 14.2 `PriceCache.version` read outside the lock (RESOLVED)

```python
@property
def version(self) -> int:
    return self._version
```

Read `self._version` without acquiring `self._lock`. On CPython (GIL), a
single `int` read is atomic, so this was safe on the deployment target, and
was originally accepted on the grounds that locking adds contention to the
SSE hot path.

**Fixed** — the property now takes the lock. The contention argument didn't
hold up: `version` is read twice per second per connected client, and an
uncontended `Lock` acquisition is on the order of tens of nanoseconds, so the
cost is unmeasurable next to the JSON serialization happening on the same
path. Taking the lock makes `PriceCache` uniformly thread-safe rather than
thread-safe-by-CPython-implementation-detail, including on free-threaded
builds (PEP 703).

### 14.3 Module-level `router` in `stream.py` (RESOLVED)

`stream.py` created one module-level `router` and `create_stream_router()`
registered `/prices` on it via closure. Calling `create_stream_router` twice
registered the route twice, and — worse than the duplicate — every
registered route closed over whichever `PriceCache` was passed last, since
they all shared the one router object.

**Fixed** — the `APIRouter` is constructed inside `create_stream_router()`,
so each call returns an independent router bound to its own cache. This is
what makes the SSE tests in §13.6 safe to write per-test-function rather than
per-session.

---

## 15. Configuration Summary

| Env var | Read by | Effect |
|---|---|---|
| `MASSIVE_API_KEY` | `factory.create_market_data_source()` only | Non-empty (after `.strip()`) → `MassiveDataSource`; unset/empty/whitespace → `SimulatorDataSource` |

| Constructor default | Value | Where |
|---|---|---|
| `SimulatorDataSource.update_interval` | `0.5` (500ms) | `simulator.py` |
| `SimulatorDataSource` event probability | `0.001` (~0.1%/tick/ticker) | `simulator.py` |
| `MassiveDataSource.poll_interval` | `15.0` (15s, free-tier safe) | `massive_client.py` |
| SSE `_generate_events` interval | `0.5` (500ms) | `stream.py` |

There is currently no env var to change `MassiveDataSource.poll_interval`
for a paid Massive plan — it's a constructor argument today (§16 covers
what adding one would look like).

---

## 16. Extension Points

- **A third data source** (a different vendor, or a WebSocket-based one)
  only needs to implement `MarketDataSource` and be wired into
  `create_market_data_source()` — zero changes to `stream.py`, portfolio
  code, or the frontend, because all of them depend only on `PriceCache`.
- **Configurable Massive poll interval for paid plans** — `factory.py`
  currently always constructs `MassiveDataSource` with the class default
  (`15.0`). Reading a second env var (e.g., `MASSIVE_POLL_INTERVAL`) and
  passing it through is a small, additive change:
  ```python
  poll_interval = float(os.environ.get("MASSIVE_POLL_INTERVAL", "15.0"))
  return MassiveDataSource(api_key=api_key, price_cache=price_cache, poll_interval=poll_interval)
  ```
- **Historical bars for chart seeding** — `MASSIVE_API.md` documents the
  `/v2/aggs/ticker/{ticker}/range/...` endpoint for historical minute/day
  bars. Not used today because the frontend chart accumulates purely from
  the live SSE stream since page load (`PLAN.md` §10) — but if a "seed the
  chart with the last hour" feature is ever wanted, it would live as a new
  method on `MassiveDataSource` (or a separate one-shot helper), not as a
  change to the streaming path.
