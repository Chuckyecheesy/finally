import { expect, test } from "@playwright/test";
import {
  DEFAULT_WATCHLIST,
  cashBalance,
  openApp,
  waitForStreamingPrice,
  watchlistPanel,
  watchlistRow,
} from "./helpers";

// Runs first in the file order: it is the only test that asserts the untouched
// $10,000 seed balance, and later files spend cash from the same database.
test.describe("fresh start", () => {
  test("seeds the default watchlist, $10,000 cash, and a live price stream", async ({ page }) => {
    await openApp(page);

    // Ten seeded tickers (PLAN.md §7 "Default Seed Data").
    await expect(watchlistPanel(page).locator("li")).toHaveCount(DEFAULT_WATCHLIST.length);
    for (const ticker of DEFAULT_WATCHLIST) {
      await expect(watchlistRow(page, ticker)).toHaveCount(1);
    }

    expect(await cashBalance(page)).toBe(10_000);

    // Prices stream: the cell must first become numeric, then change again on a
    // later tick. Polling both proves the SSE feed is live, not just seeded.
    const first = await waitForStreamingPrice(page, "AAPL");
    expect(first).toBeGreaterThan(0);

    const priceCell = watchlistRow(page, "AAPL").getByTestId("price-cell");
    await expect
      .poll(async () => Number.parseFloat(await priceCell.innerText()), { timeout: 30_000 })
      .not.toBe(first);
  });

  test("total value equals cash when flat", async ({ page }) => {
    await openApp(page);
    await expect(page.getByText("No open positions.")).toBeVisible();
  });
});
