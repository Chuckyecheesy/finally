# Codebase Concerns

**Analysis Date:** 2026-08-16

## Security Considerations

**Live API key present in a tracked, modified file — highest priority:**
- Risk: `.env.example` (tracked by git, meant to be a template with a placeholder) currently has an **uncommitted working-tree modification** that replaces the placeholder `OPENROUTER_API_KEY=your-openrouter-api-key-here` with what appears to be a real, live OpenRouter key (`sk-or-v1-...`). This was found via `git diff .env.example`.
- Files: `.env.example` (repo root)
- Impact: if this change is ever committed and pushed, the key is permanently in git history and publicly exposed if the repo is public; even locally it risks being picked up by any tooling that reads `.env.example` as a real env file, or being accidentally committed by a future `git add -A`.
- Fix approach: revert `.env.example` to the placeholder value immediately (`git checkout -- .env.example` or manually restore the placeholder), rotate the real OpenRouter key since it may already be exposed on this machine's shell history/screen sharing, and add a pre-commit check (e.g. gitleaks or a simple grep hook) that blocks commits containing `sk-or-v1-` style tokens in any file. Never commit real secrets into `*.example` files — only `.env` (already gitignored) should hold them.

**Runtime SQLite database file committed to git:**
- Risk: `db/finally.db` (100KB binary SQLite file) is tracked in git (`git ls-files db/` confirms it), even though PLAN.md §4 explicitly states "`db/finally.db` is gitignored" and only `.gitkeep` should be committed at that path.
- Files: `db/finally.db`, `.gitignore`
- Impact: `.gitignore` only excludes `db.sqlite3` / `db.sqlite3-journal` (leftover Django-template patterns), not the actual `db/finally.db` path this project uses. Every local run of the app mutates this file (trades, chat history, watchlist changes, portfolio snapshots), so it will show as a dirty/binary diff on every `git status` and risks committing one developer's local trading session data into shared history, plus merge conflicts on a binary file.
- Recommendation: add `db/*.db`, `db/*.db-wal`, `db/*.db-shm` to `.gitignore`, `git rm --cached db/finally.db`, and commit a `db/.gitkeep` per the directory structure documented in PLAN.md §4.

**No input validation on ticker symbols beyond non-blank:**
- Risk: `POST /api/watchlist` (`backend/app/api/watchlist.py`) and trade execution accept any non-empty string as a ticker (by design per PLAN.md §8), normalized only via `normalize_ticker()` in `backend/app/market/interface.py`. This is a deliberate product decision, not a bug, but it means arbitrary user-supplied strings flow into the LLM's portfolio context (`backend/app/llm/context.py`) unescaped.
- Files: `backend/app/api/watchlist.py`, `backend/app/llm/context.py`
- Current mitigation: none beyond length/blank checks.
- Recommendation: low priority given single-user, no-auth design, but if this ever gains multi-user or public-facing use, add a length cap and character allowlist for tickers before they reach the LLM prompt context (prompt-injection surface).

**Single-user, no-auth design has zero access control:**
- Risk: every table hardcodes `user_id="default"`; there is no authentication anywhere in the stack (by design per PLAN.md §7). If deployed publicly (PLAN.md §11 mentions optional AWS App Runner / Render deployment), anyone reaching the port has full read/write access to the one account, including AI-driven trade execution.
- Files: `backend/app/db/*.py` (all use `DEFAULT_USER_ID`), `backend/app/main.py`
- Recommendation: acceptable for the stated local-single-user use case; must not be deployed to a public endpoint without adding auth first. Worth a prominent warning in the deployment docs if `deploy/` is ever built out.

## Fragile Areas

**`app/main.py`'s `_DeferredMarketSource` indirection:**
- Files: `backend/app/main.py` (`_DeferredMarketSource` class, `_include_chat_router`)
- Why fragile: the chat router is constructed before the FastAPI `lifespan` has started the real market data source, so it's handed a proxy object (`_DeferredMarketSource`) that looks up `app.state.market_source` lazily on every call and raises `RuntimeError` if accessed before startup completes. This is a reasonable workaround but is easy to break: any future refactor that constructs `create_chat_router` differently, or that accesses `market_source` synchronously during router construction, will silently swallow the real source and fail at request time instead of at startup.
- Safe modification: keep chat-router construction happening strictly inside `create_app()` after the other routers, and route all access to the market source through `app.state.market_source` rather than capturing it directly.
- Test coverage: `backend/tests/api/test_app.py` exists but should be checked for explicit coverage of the pre-startup-access RuntimeError path when the LLM router is present.

**`_include_chat_router` silently no-ops if `app.llm.router` fails to import:**
- Files: `backend/app/main.py` (`_include_chat_router`)
- Why fragile: any `ImportError` from `app.llm.router` (including a transitive one, e.g. from a broken `litellm` import) is caught broadly and logged as a warning, then the app boots without `/api/chat` mounted at all — no error surfaced to callers of that endpoint, they'd just get a 404. This was designed to let backend and LLM work land independently during initial development, but it's now dead flexibility since `app.llm.router` exists and is wired up. It also means a real bug inside `litellm`'s import chain (a large, frequently-updated dependency) degrades the whole chat feature invisibly.
- Fix approach: now that the LLM module is complete, replace the broad `except ImportError` with a hard import at module level, or narrow the except clause and log at `error` level with a startup-time health check that flags `/api/chat` as unavailable via `/api/health`.

**Portfolio valuation falls back to average cost when price cache is empty:**
- Files: `backend/app/api/portfolio.py` (`build_portfolio`)
- Why fragile: if a ticker is in `positions` but missing from `price_cache` (e.g., Massive API never returned data for it, per PLAN.md §5's "no fallback to simulator" behavior), `current_price` silently becomes `avg_cost`, which reports 0% unrealized P&L rather than surfacing a "stale/unknown price" state to the user. This is called out as intentional in the code comment, but it means a real trading session using Massive with a bad/rate-limited key could show a portfolio that looks fine while actually being priced on stale cost-basis data indefinitely.
- Safe modification: if extending this, add a `stale: bool` flag to `PositionOut` so the frontend can visually distinguish "priced at cost because no market data" from a genuine break-even position.

**GBM simulator correlation matrix (Cholesky decomposition) at scale:**
- Files: `backend/app/market/simulator.py` (273 lines, largest backend module)
- Why fragile: correlated multi-ticker price generation via Cholesky decomposition is numerically sensitive — the `MARKET_DATA_SUMMARY.md` notes a prior fix was needed to make the full 10-ticker correlation matrix "well-behaved." Adding many tickers to the watchlist (arbitrarily allowed per PLAN.md §8, since any string is accepted) grows the correlation matrix and could reintroduce numerical instability (non-positive-definite matrix) that wasn't covered by the original 10-ticker test.
- Test coverage: `backend/tests/market/test_simulator.py` covers the full default 10-ticker set; no test exercises a large (e.g., 50+) or adversarial (all newly-added, non-default) ticker set for Cholesky stability.

## Performance Considerations

**Frontend polls REST endpoints on a fixed 15s timer in addition to SSE:**
- Files: `frontend/src/hooks/useTerminal.ts` (`refresh`, `setInterval(... 15_000)`)
- Problem: `fetchPortfolio`, `fetchWatchlist`, and `fetchHistory` are re-fetched every 15 seconds regardless of whether anything changed, on top of the live SSE price stream. This is a deliberate reconciliation mechanism (SSE only carries prices, not position/cash changes from other tabs or the AI), but it's a fixed poll with no backoff and no visibility/tab-focus gating — a backgrounded browser tab keeps polling every 15s indefinitely.
- Improvement path: gate the interval on `document.visibilityState`, or switch position/cash sync to be pushed via SSE alongside prices so the poll becomes a rarer reconciliation fallback rather than the primary sync path.

**Snapshot task and trade-triggered snapshot both write within the same 30s window:**
- Files: `backend/app/main.py` (`_snapshot_loop`), `backend/app/api/portfolio.py` (`post_trade`)
- Problem: PLAN.md §7 calls for a snapshot on trade plus a snapshot every 30s; under active trading (e.g., several AI-driven trades in one chat turn per PLAN.md §9's sequential multi-trade execution), this can produce many near-duplicate `portfolio_snapshots` rows in quick succession, since `execute_watchlist_changes`/`execute_trades` don't dedupe against the periodic loop.
- Impact: unbounded growth of `portfolio_snapshots` over a long session; `GET /api/portfolio/history` (`backend/app/db/snapshots.py`) has no pagination or time-range limiting, so a chart re-fetch grows linearly with session length and could become slow after many hours of active use.
- Improvement path: add a `LIMIT`/downsampling parameter to `list_snapshots`, or debounce trade-triggered snapshots that land within a few seconds of the last one.

## Test Coverage Gaps

**No dedicated tests for `_DeferredMarketSource` or `_include_chat_router` import-failure path:**
- What's not tested: `backend/app/main.py`'s startup-ordering workaround and the silent-fallback behavior when `app.llm.router` can't be imported.
- Files: `backend/app/main.py`, `backend/tests/api/test_app.py`
- Risk: a regression here (e.g., chat router accidentally captures `None` instead of the deferred proxy) would only surface as every AI-driven watchlist change failing at runtime, not at test time.
- Priority: Medium.

**No E2E coverage confirming Massive-API-key path end-to-end:**
- What's not tested: `test/tests/*.spec.ts` all run with `MASSIVE_API_KEY=""` (simulator only) per `test/docker-compose.test.yml`. There is unit coverage of `massive_client.py`'s parsing logic (`backend/tests/market/test_massive.py`, 34 tests) but no integration/E2E test exercises a real or realistically-mocked Massive polling cycle feeding the SSE stream and portfolio valuation together.
- Files: `test/docker-compose.test.yml`, `backend/app/market/massive_client.py`
- Risk: given that a prior real bug (wrong timestamp field, see `planning/MARKET_DATA_SUMMARY.md` item 8) was previously found only by manual inspection against the real API shape, another such regression could reappear undetected since only unit-level mocks exercise this path.
- Priority: Medium (mitigated by the extensive unit tests, but no integration safety net).

**Frontend visual components without unit tests:**
- What's not tested: `frontend/src/components/Heatmap.tsx`, `PnlChart.tsx`, `PriceChart.tsx`, `Sparkline.tsx`, `TradeBar.tsx`, `Panel.tsx` have no corresponding `*.test.tsx` files (only `ChatPanel`, `Header`, `PositionsTable`, `PriceCell`, `Watchlist`, and the `usePriceStream` hook do, per `frontend/src/components/*.test.tsx`).
- Files: listed above under `frontend/src/components/`
- Risk: the treemap fill-color math (`fillFor` in `Heatmap.tsx`), sparkline SVG path generation, and trade-bar validation logic (`valid`/`notional` computation in `TradeBar.tsx`) are pure-enough to unit test cheaply but currently rely entirely on the Playwright E2E suite (`test/tests/04-visualization.spec.ts`, `03-trading.spec.ts`) for coverage, which is slower and less precise for catching regressions in these calculations.
- Priority: Low — E2E suite provides a safety net, but a regression in `fillFor`'s intensity math wouldn't fail loudly, just look visually wrong.

## Dependencies at Risk

**`litellm` is a very large, fast-moving dependency:**
- Risk: `backend/.venv` shows `litellm` 1.96.2 as one of the largest vendored packages in the project (`proxy_server.py` alone is ~16,800 lines), and only a thin slice of its surface (`litellm.completion` with `response_format`) is actually used, per `backend/app/llm/client.py`.
- Impact: frequent upstream releases increase the chance of a breaking change to the `completion()` signature, structured-output handling, or the `extra_body={"provider": {"order": ["cerebras"]}}` OpenRouter-specific parameter shape, silently breaking the one call site.
- Migration plan: `backend/app/llm/client.py` already isolates all LiteLLM usage behind `generate_response()` with broad exception handling that degrades to an apology message rather than crashing (good defensive design already in place); if litellm's breaking-change rate becomes a problem, consider pinning more tightly in `backend/uv.lock` (already locked) and adding a CI check that calls `generate_response` against a cheap live request before deploys.

**Frontend dependencies are one to two minor/major versions behind latest:**
- Risk: `npm outdated` shows `next` (15.5.23 → 16.3.1), `eslint` (9.18.0 → 10.8.1), `typescript` (5.7.3 → 7.0.2), `react`/`react-dom` (19.0.0 → 19.2.8) all have newer versions available.
- Impact: low urgency — nothing here is a known-vulnerable version, this is normal drift — but `typescript` is a full major version behind, and `next` static export behavior (`output: 'export'`, central to the single-container deployment strategy in PLAN.md §3) is worth re-verifying against next's release notes before upgrading given how load-bearing the static export is to the whole Docker architecture.
- Migration plan: no action required now; treat as routine maintenance, and test the static export (`npm run build` producing `frontend/out/`, consumed by `Dockerfile`) explicitly after any `next` upgrade since that's the single point where a regression would silently break the production image.

## Missing Critical Features

**No pagination/limit on chat history growth beyond the 20-message context window:**
- Problem: PLAN.md §9 caps LLM prompt context to the last 20 messages, but `chat_messages` itself is an unbounded append-only log with no retention policy or UI for browsing/clearing old history (`backend/app/db/chat.py`).
- Blocks: a very long-running session accumulates an ever-growing table with no way to trim it short of manually deleting the SQLite file; not urgent for a demo/course project but worth flagging if this becomes a longer-lived deployment.

---

*Concerns audit: 2026-08-16*
