import { expect, test, type Page } from "@playwright/test";
import { openApp, waitForConnected, waitForStreamingPrice } from "./helpers";

const STREAM = "**/api/stream/prices";

const dot = (page: Page) => page.getByTestId("connection-dot");

test("the indicator reports a healthy stream", async ({ page }) => {
  await openApp(page);
  await expect(dot(page)).toHaveAttribute("data-status", "connected");
  await expect(page.getByRole("status")).toHaveText("Live");
});

test("a dropped stream is reported, then EventSource reconnects on its own", async ({ page }) => {
  // `context.setOffline` does not tear down an already-open SSE response, so the
  // drop is staged at the network layer instead: the first stream request is
  // answered with a short, *finite* event stream. The browser opens it (which is
  // what marks the connection as having been live), then hits EOF — exactly the
  // shape of a server going away mid-stream. Later retries are aborted so the
  // UI stays in its failed state long enough to assert on, deterministically.
  let served = 0;
  await page.route(STREAM, async (route) => {
    served += 1;
    if (served > 1) return route.abort();
    await route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream", "cache-control": "no-cache" },
      body:
        "retry: 1000\n" +
        'data: {"AAPL":{"ticker":"AAPL","price":190.00,"previous_price":189.50,' +
        '"timestamp":1,"direction":"up"}}\n\n',
    });
  });

  await page.goto("/");

  // Stream opened and then died: the header must surface the failure.
  await expect(dot(page)).toHaveAttribute("data-status", "reconnecting", { timeout: 20_000 });
  await expect(page.getByRole("status")).toHaveText("Reconnecting");

  // Let the backend answer again. No reload, no user action — EventSource's own
  // retry has to bring the terminal back.
  await page.unroute(STREAM);

  await waitForConnected(page);
  await expect(page.getByRole("status")).toHaveText("Live");

  // Recovery means live data again, not just a green dot.
  const price = await waitForStreamingPrice(page, "AAPL");
  const cell = page
    .getByRole("region", { name: "Watchlist" })
    .locator("li")
    .filter({ has: page.getByText("AAPL", { exact: true }) })
    .getByTestId("price-cell");
  await expect
    .poll(async () => Number.parseFloat(await cell.innerText()), { timeout: 30_000 })
    .not.toBe(price);
});

test("a page reload re-establishes the stream", async ({ page }) => {
  await openApp(page);
  await page.reload();
  await waitForConnected(page);
  expect(await waitForStreamingPrice(page, "GOOGL")).toBeGreaterThan(0);
});
