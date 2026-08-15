# Unified Market Data Interface

This document specifies the Python API FinAlly's backend uses to retrieve
live stock prices, regardless of whether the data comes from the Massive API
or the built-in simulator. It reflects the implementation already built in
`backend/app/market/` (see `planning/MARKET_DATA_SUMMARY.md` for the delivery
summary); this doc is the design reference for that code.

Background on the Massive API itself is in `MASSIVE_API.md`. The simulator's
internal math and structure is in `MARKET_SIMULATOR.md`.

## Design Goals

1. **Source-agnostic downstream code.** SSE streaming, portfolio valuation,
   and trade execution must not know or care whether prices come from GBM
   simulation or a real REST poller.
2. **One shared mutable point of truth.** A single in-memory cache that
   producers write to and consumers read from, decoupling production rate
   from consumption rate.
3. **Dynamic ticker set.** The watchlist changes at runtime (user adds/removes
   tickers, or the AI chat does it on their behalf); both sources must be able
   to start tracking a new ticker or stop tracking one without a restart.
4. **Fail stale, not silent-fallback.** Per `planning/PLAN.md` §5, a failed
   Massive poll does not fall back to the simulator — it logs and retries,
   leaving the cache stale for affected tickers.

## The Three Pieces

```
MarketDataSource (ABC)          — what a producer must implement
        ├── SimulatorDataSource
        └── MassiveDataSource
                │
                ▼
         PriceCache             — the shared point of truth
                │
                ▼
      PriceUpdate                — the unit of data moving through the system
```

### `PriceUpdate` — the data unit

`backend/app/market/models.py`

```python
@dataclass(frozen=True, slots=True)
class PriceUpdate:
    ticker: str
    price: float
    previous_price: float
    timestamp: float = field(default_factory=time.time)  # Unix seconds

    @property
    def change(self) -> float: ...          # price - previous_price
    @property
    def change_percent(self) -> float: ...  # % change, 0.0 if previous_price == 0
    @property
    def direction(self) -> str: ...          # "up" | "down" | "flat"

    def to_dict(self) -> dict: ...           # JSON-serializable, used directly for SSE payloads
```

Immutable and frozen so a `PriceUpdate` handed to an SSE consumer can never be
mutated out from under it mid-serialization. `timestamp` is always **Unix
seconds** internally — any producer working in a different unit (Massive's
nanosecond timestamps) must convert before calling `PriceCache.update()`.

### `PriceCache` — the shared point of truth

`backend/app/market/cache.py`

```python
class PriceCache:
    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate: ...
    def get(self, ticker: str) -> PriceUpdate | None: ...
    def get_price(self, ticker: str) -> float | None: ...
    def get_all(self) -> dict[str, PriceUpdate]: ...
    def remove(self, ticker: str) -> None: ...

    @property
    def version(self) -> int: ...   # monotonic counter, bumped on every update()
```

- Thread-safe via a single `Lock` — needed because `MassiveDataSource` runs
  its HTTP calls via `asyncio.to_thread`, so writes may originate off the
  event loop thread.
- `update()` computes `previous_price` from whatever was cached before (or
  equals `price` on first write, giving `direction == "flat"` for a ticker's
  very first tick — avoids a spurious green/red flash on initial load).
  `price` and `previous_price` are rounded to 2 decimals on write.
  Callers do not construct `PriceUpdate` directly; `update()` is the only
  write path.
- `version` exists purely so the SSE endpoint can cheaply detect "did
  anything change since I last sent an event" without diffing dictionaries
  (see `stream.py`'s `_generate_events`, which polls `version` every 500ms
  and only serializes+sends when it has changed).

### `MarketDataSource` — the producer contract

`backend/app/market/interface.py`

```python
class MarketDataSource(ABC):
    async def start(self, tickers: list[str]) -> None: ...
    async def stop(self) -> None: ...
    async def add_ticker(self, ticker: str) -> None: ...
    async def remove_ticker(self, ticker: str) -> None: ...
    def get_tickers(self) -> list[str]: ...
```

Lifecycle contract:

```python
source = create_market_data_source(cache)
await source.start(["AAPL", "GOOGL", ...])   # exactly once
await source.add_ticker("TSLA")               # any time after start()
await source.remove_ticker("GOOGL")           # any time after start()
await source.stop()                           # idempotent; safe to call repeatedly
```

Both implementations own a background `asyncio.Task` created in `start()` and
cancelled in `stop()`. Neither implementation returns prices directly to the
caller — they only ever write into the injected `PriceCache`. This is the
core of the strategy pattern: nothing outside `app/market/` imports
`SimulatorDataSource` or `MassiveDataSource` by name.

### `create_market_data_source()` — the selector

`backend/app/market/factory.py`

```python
def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if api_key:
        return MassiveDataSource(api_key=api_key, price_cache=price_cache)
    return SimulatorDataSource(price_cache=price_cache)
```

This is the **only** place the `MASSIVE_API_KEY` env var is read for
data-source selection, and the only place that decides simulator vs. real
data. Callers (`app/main.py` at startup) never branch on the env var
themselves — they just call this factory and get back something satisfying
`MarketDataSource`.

## Implementation Comparison

| | `SimulatorDataSource` | `MassiveDataSource` |
|---|---|---|
| Update cadence | 500ms, in-process loop | 15s poll (free tier), one REST call per poll covering all tickers |
| Data origin | GBM math, see `MARKET_SIMULATOR.md` | `GET /v2/snapshot/locale/us/markets/stocks/tickers` |
| Blocking calls | None — pure Python/numpy | Yes — `RESTClient` is sync, wrapped in `asyncio.to_thread` |
| First-write latency | Cache seeded synchronously inside `start()`, before the loop task is spawned | An immediate `_poll_once()` call inside `start()`, before the poll-loop task is spawned |
| Failure behavior | N/A (no external dependency to fail) | Catches all exceptions per poll, logs, retries next interval — cache goes stale, never falls back to simulator |
| `add_ticker` latency | Immediate — cache seeded with a fresh simulated price synchronously | Deferred — ticker is added to the tracked list but the cache isn't updated until the next scheduled poll |

Both `start()` implementations follow the same shape deliberately: seed the
cache with an initial value *before* returning, so that whatever endpoint or
task reads the cache next (e.g., the first SSE frame) never sees an empty
result for a ticker that's supposedly being tracked.

## Known Issue: Massive Timestamp Field

`MassiveDataSource._poll_once()` (in `massive_client.py`) currently does:

```python
timestamp = snap.last_trade.timestamp / 1000.0
```

The installed `massive` client's `LastTrade` model
(`massive.rest.models.trades.LastTrade`) has no `.timestamp` attribute — the
JSON field `t` (a Unix-nanosecond trade timestamp) is exposed as
**`.sip_timestamp`**. Accessing `.timestamp` raises `AttributeError`, which
`_poll_once()` catches per-snapshot and logs as a warning
(`"Skipping snapshot for %s: %s"`) — so with a real `MASSIVE_API_KEY` set,
every poll currently logs a skip for every ticker and the price cache is
never populated. See `MASSIVE_API.md` for the field reference. The fix is
two-part: read `snap.last_trade.sip_timestamp`, and divide by `1e9` (not
`1000.0`) since the units are nanoseconds, not milliseconds.

This document records the issue as the interface's contract reference;
fixing it is implementation work outside the scope of these planning docs.

## Extension Points

- **A third data source** (e.g., a different vendor) only needs to implement
  `MarketDataSource` and be wired into `create_market_data_source()` — no
  changes anywhere else, including the SSE stream, portfolio code, or
  frontend.
- **Sub-15s Massive polling on a paid plan** is just a constructor argument
  change (`MassiveDataSource(poll_interval=...)`); the factory could read a
  second env var to pick the interval, but that's not implemented today —
  `factory.py` always constructs with the class default.
