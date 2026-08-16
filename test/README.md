# E2E tests

Playwright suite covering the "Key Scenarios" in `planning/PLAN.md` §12. It
drives the real production image — the app built from the repo-root
`Dockerfile` — with `LLM_MOCK=true` and no `MASSIVE_API_KEY`, so the assistant
is deterministic and prices come from the built-in simulator.

## Run everything in Docker

```bash
docker compose -f test/docker-compose.test.yml up --build \
  --abort-on-container-exit --exit-code-from playwright
docker compose -f test/docker-compose.test.yml down -v
```

The app's database lives on a `tmpfs`, never the host `db/` directory, so every
run starts from freshly seeded data ($10,000 cash, the ten default tickers).

## Run against the container from your host

The compose file publishes the app on port 8000 (override with `E2E_APP_PORT`).

```bash
docker compose -f test/docker-compose.test.yml up -d --build app
cd test && npm install && npx playwright install chromium && npx playwright test
```

Restart the `app` service to reset the database between runs.

## Notes

- The suite is serial (`workers: 1`) and files run in numeric order: one app
  container means one shared database, and `01-fresh-start` is the only spec
  that may assume an untouched $10,000 balance.
- Chat assertions depend on the trigger phrases documented in
  `backend/app/llm/mock.py`'s module docstring. Change them there and the chat
  specs must follow.
