import { expect, test } from "@playwright/test";
import {
  cashBalance,
  openApp,
  positionRow,
  positionsPanel,
  totalValue,
  trade,
  waitForStreamingPrice,
} from "./helpers";

const TICKER = "MSFT";

test.describe.configure({ mode: "serial" });

test("buying shares debits cash and opens a position", async ({ page }) => {
  await openApp(page);
  const price = await waitForStreamingPrice(page, TICKER);

  const cashBefore = await cashBalance(page);
  const totalBefore = await totalValue(page);

  await trade(page, TICKER, 4, "buy");

  const row = positionRow(page, TICKER);
  await expect(row).toHaveCount(1);
  await expect(row.locator("td").nth(1)).toHaveText("4");

  const cashAfter = await cashBalance(page);
  expect(cashAfter).toBeLessThan(cashBefore);
  // Fill price is whatever the stream held at execution; allow generous drift.
  expect(cashBefore - cashAfter).toBeGreaterThan(price * 4 * 0.8);
  expect(cashBefore - cashAfter).toBeLessThan(price * 4 * 1.2);

  // Total value is cash + market value, so a buy should not move it much.
  expect(Math.abs((await totalValue(page)) - totalBefore)).toBeLessThan(price * 4 * 0.25);
});

test("selling part of a position credits cash and reduces quantity", async ({ page }) => {
  await openApp(page);
  await waitForStreamingPrice(page, TICKER);
  await expect(positionRow(page, TICKER)).toHaveCount(1);

  const cashBefore = await cashBalance(page);

  await trade(page, TICKER, 1.5, "sell");

  await expect(positionRow(page, TICKER).locator("td").nth(1)).toHaveText("2.5");
  expect(await cashBalance(page)).toBeGreaterThan(cashBefore);
});

test("selling the remaining shares removes the position", async ({ page }) => {
  await openApp(page);
  await waitForStreamingPrice(page, TICKER);

  const cashBefore = await cashBalance(page);
  await trade(page, TICKER, 2.5, "sell");

  await expect(positionRow(page, TICKER)).toHaveCount(0);
  await expect(positionsPanel(page).getByText("No open positions.")).toBeVisible();
  expect(await cashBalance(page)).toBeGreaterThan(cashBefore);
});

test("overselling is rejected with an inline error", async ({ page }) => {
  await openApp(page);
  await waitForStreamingPrice(page, "JPM");

  const cashBefore = await cashBalance(page);
  await trade(page, "JPM", 5, "sell");

  // Next.js renders its own empty role="alert" route announcer, so match on text.
  const error = page.getByRole("alert").filter({ hasText: /Insufficient shares/ });
  await expect(error).toBeVisible();
  expect(await cashBalance(page)).toBe(cashBefore);

  await error.getByRole("button", { name: "Dismiss error" }).click();
  await expect(error).toHaveCount(0);
});
