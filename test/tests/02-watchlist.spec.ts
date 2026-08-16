import { expect, test } from "@playwright/test";
import {
  openApp,
  selectTicker,
  waitForStreamingPrice,
  watchlistPanel,
  watchlistRow,
} from "./helpers";

const NEW_TICKER = "PYPL";

test("add and remove a watchlist ticker through the UI", async ({ page }) => {
  await openApp(page);

  const before = await watchlistPanel(page).locator("li").count();
  await expect(watchlistRow(page, NEW_TICKER)).toHaveCount(0);

  await watchlistPanel(page).getByLabel("Add ticker").fill(NEW_TICKER);
  await watchlistPanel(page).getByRole("button", { name: "+" }).click();

  await expect(watchlistRow(page, NEW_TICKER)).toHaveCount(1);
  await expect(watchlistPanel(page).locator("li")).toHaveCount(before + 1);

  // A newly watched ticker must join the tracked set and start streaming.
  expect(await waitForStreamingPrice(page, NEW_TICKER)).toBeGreaterThan(0);

  await watchlistRow(page, NEW_TICKER)
    .getByRole("button", { name: `Remove ${NEW_TICKER} from watchlist` })
    .click();

  await expect(watchlistRow(page, NEW_TICKER)).toHaveCount(0);
  await expect(watchlistPanel(page).locator("li")).toHaveCount(before);
});

test("selecting a watchlist ticker drives the chart and order entry", async ({ page }) => {
  await openApp(page);

  await selectTicker(page, "TSLA");

  await expect(page.getByLabel("Ticker", { exact: true })).toHaveValue("TSLA");
  await expect(page.getByRole("region", { name: /TSLA/ })).toBeVisible();
});
