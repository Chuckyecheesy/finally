# Market Simulator — Design & Code Structure

The simulator is FinAlly's default market data source (used whenever
`MASSIVE_API_KEY` is unset — see `MARKET_INTERFACE.md`). It generates
plausible, correlated stock price paths in-process with no external
dependencies, so the app is fully usable offline / without an API key. This
document describes the approach implemented in `backend/app/market/simulator.py`
and `backend/app/market/seed_prices.py`.

## Why GBM

Geometric Brownian Motion is the standard toy model for a stock price: it
guarantees prices stay positive, produces the familiar random-walk-with-drift
look, and is cheap to compute per tick. It's not meant to be a realistic
market microstructure model — it's meant to *look and feel* like a market
ticker for a demo, tick every 500ms, for as long as a browser tab stays open.

### The Formula

```
S(t+dt) = S(t) * exp((mu - sigma^2/2) * dt + sigma * sqrt(dt) * Z)
```

- `S(t)` — current price
- `mu` — annualized drift (expected return)
- `sigma` — annualized volatility
- `dt` — time step, expressed as a fraction of a trading year
- `Z` — a standard normal random draw (correlated across tickers, see below)

### Choosing `dt`

The simulator ticks every 500ms but `mu`/`sigma` are *annualized*
parameters, so `dt` has to convert "500ms" into "fraction of a trading year":

```python
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600   # 5,896,800 (252 trading days, 6.5h/day)
DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR   # ≈ 8.48e-8
```

This tiny `dt` is deliberate: it produces sub-cent moves per 500ms tick that
accumulate into realistic-looking intraday volatility over a session, rather
than wild jumps every half second.

## Correlated Moves (Cholesky)

Real markets don't move ticker-by-ticker independently — tech stocks tend to
move together, financials tend to move together. The simulator reproduces
this by drawing correlated normal variables instead of independent ones:

1. Build an `n x n` correlation matrix where `n` = number of tracked tickers,
   using a fixed sector-based correlation structure (see below).
2. Compute its Cholesky decomposition `L` once, whenever the ticker set
   changes (`add_ticker`/`remove_ticker` trigger a rebuild — O(n²), cheap
   for `n < 50`).
3. Each tick: draw `n` independent standard normals `z_independent`, then
   `z_correlated = L @ z_independent` gives normals with the target
   correlation structure. This runs on every 500ms tick, so it's kept to a
   single matrix-vector multiply (`numpy`), not recomputed from scratch.

### Correlation Structure (`seed_prices.py`)

```python
CORRELATION_GROUPS = {
    "tech": {"AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "NFLX"},
    "finance": {"JPM", "V"},
}

INTRA_TECH_CORR = 0.6      # two tech tickers move together
INTRA_FINANCE_CORR = 0.5   # two finance tickers move together
CROSS_GROUP_CORR = 0.3     # tech vs finance, or either vs. an unknown ticker
TSLA_CORR = 0.3            # TSLA is deliberately excluded from the tech group's high correlation
```

Pairwise correlation is resolved with a simple lookup (`_pairwise_correlation`):
TSLA takes priority (always 0.3, "does its own thing"), then same-tech,
then same-finance, then a flat 0.3 for everything else — including any
ticker outside the known set entirely.

## Per-Ticker Parameters & Seed Prices

`seed_prices.py` holds three lookup tables, all keyed by ticker symbol:

```python
SEED_PRICES: dict[str, float]              # starting price
TICKER_PARAMS: dict[str, dict[str, float]] # {"sigma": ..., "mu": ...} per ticker
DEFAULT_PARAMS: dict[str, float]           # fallback for unrecognized tickers
```

The default watchlist's 10 tickers each get a hand-picked realistic seed
price and volatility profile — e.g. `TSLA` at `sigma=0.50` (high volatility)
vs. `JPM` at `sigma=0.18` (low volatility, "it's a bank"). Per
`planning/PLAN.md` §6, **any** ticker string can be added to the watchlist at
runtime — not just the known 10 — so unrecognized tickers fall back to:

```python
SEED_PRICES.get(ticker, random.uniform(50.0, 300.0))
TICKER_PARAMS.get(ticker, dict(DEFAULT_PARAMS))   # sigma=0.25, mu=0.05
```

This is what makes "add any symbol to the watchlist" work without the
simulator needing a real quote to seed from.

## Random Events

Beyond smooth GBM drift, each tick has a small independent chance of a
sudden jump on any given ticker, for visual drama on the dashboard:

```python
event_probability = 0.001   # ~0.1% chance per tick per ticker
if random.random() < event_probability:
    shock_magnitude = random.uniform(0.02, 0.05)   # 2-5% move
    shock_sign = random.choice([-1, 1])
    price *= 1 + shock_magnitude * shock_sign
```

With 10 tickers ticking twice a second, this works out to roughly one
noticeable jump every ~50 seconds somewhere in the watchlist — often enough
to be visible during a demo, rare enough not to dominate the price action.

## Code Structure

```
backend/app/market/
├── seed_prices.py   — static data: SEED_PRICES, TICKER_PARAMS, DEFAULT_PARAMS,
│                       CORRELATION_GROUPS, correlation constants
└── simulator.py      — GBMSimulator (pure math/state) + SimulatorDataSource
                          (async wrapper satisfying MarketDataSource)
```

### `GBMSimulator` — pure simulation state, no asyncio

```python
class GBMSimulator:
    def __init__(self, tickers: list[str], dt: float = DEFAULT_DT,
                 event_probability: float = 0.001) -> None: ...

    def step(self) -> dict[str, float]:
        """Advance all tickers by one tick. Hot path — called every 500ms."""

    def add_ticker(self, ticker: str) -> None:
        """Seed a new ticker and rebuild the Cholesky decomposition."""

    def remove_ticker(self, ticker: str) -> None:
        """Drop a ticker and rebuild the Cholesky decomposition."""

    def get_price(self, ticker: str) -> float | None: ...
    def get_tickers(self) -> list[str]: ...
```

Deliberately synchronous and dependency-free (just `numpy`, `math`,
`random`) — this keeps the actual math trivially unit-testable without an
event loop, and keeps `step()` fast since it's the code that runs every
500ms for every tracked ticker.

Internal state is three parallel dicts keyed by ticker (`_prices`,
`_params`) plus an ordered `_tickers` list (list order matters — it's the
index basis for the Cholesky matrix and the correlated-draw vector, so the
matrix and the ticker list must stay in lockstep, which is why both
`add_ticker`/`remove_ticker` touch `_tickers` and immediately call
`_rebuild_cholesky()`).

### `SimulatorDataSource` — the async `MarketDataSource` adapter

```python
class SimulatorDataSource(MarketDataSource):
    def __init__(self, price_cache: PriceCache, update_interval: float = 0.5,
                 event_probability: float = 0.001) -> None: ...

    async def start(self, tickers: list[str]) -> None:
        """Construct GBMSimulator, seed the cache synchronously, spawn the loop task."""

    async def _run_loop(self) -> None:
        """while True: step() -> write every price to PriceCache -> sleep(interval)."""
```

This class owns nothing about GBM math — it only owns the asyncio task
lifecycle and translates `GBMSimulator.step()`'s `{ticker: price}` output
into `PriceCache.update()` calls. `_run_loop` wraps each step in a
try/except so a single bad tick (e.g., a numpy edge case) logs via
`logger.exception` and the loop keeps running rather than dying silently.

## Testing Approach

Per `planning/MARKET_DATA_SUMMARY.md`, the simulator has 98% line coverage
across `test_simulator.py` (17 tests, pure `GBMSimulator` math — no asyncio)
and `test_simulator_source.py` (10 tests, the async `SimulatorDataSource`
wrapper against a real `PriceCache`). Splitting the math from the asyncio
wrapper this way is what makes the math easily testable: GBM correctness,
correlation-matrix construction, and the random-event trigger can all be
asserted deterministically by seeding `numpy`/`random`, without needing to
run an event loop or sleep in tests.
