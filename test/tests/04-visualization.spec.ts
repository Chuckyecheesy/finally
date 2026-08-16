import { expect, test } from "@playwright/test";
import {
  allocationPanel,
  openApp,
  pnlPanel,
  positionRow,
  trade,
  waitForStreamingPrice,
} from "./helpers";

const TICKER = "NVDA";

test.describe.configure({ mode: "serial" });

test("allocation heatmap renders a cell per position", async ({ page }) => {
  await openApp(page);
  await waitForStreamingPrice(page, TICKER);

  await expect(allocationPanel(page).getByText(/Buy a position/)).toBeVisible();

  await trade(page, TICKER, 3, "buy");
  await expect(positionRow(page, TICKER)).toHaveCount(1);

  const cell = allocationPanel(page).getByRole("listitem", { name: new RegExp(`^${TICKER} `) });
  await expect(cell).toHaveCount(1);
  await expect(cell.locator("rect")).toHaveAttribute("fill", /color-mix/);
  // Sized by weight: a real rectangle, not a degenerate one.
  expect(Number(await cell.locator("rect").getAttribute("width"))).toBeGreaterThan(0);
});

test("P&L chart plots portfolio snapshots", async ({ page }) => {
  await openApp(page);

  // Snapshots exist from app startup and from each executed trade (PLAN.md §7),
  // and the chart draws once there are at least two of them.
  await expect(pnlPanel(page).locator("svg .recharts-line-curve")).toHaveCount(1);
  const d = await pnlPanel(page).locator("svg .recharts-line-curve").first().getAttribute("d");
  expect(d).toBeTruthy();
  expect(d!.length).toBeGreaterThan(5);
});

test("clicking a heatmap cell selects the ticker", async ({ page }) => {
  await openApp(page);
  await waitForStreamingPrice(page, TICKER);

  await allocationPanel(page)
    .getByRole("listitem", { name: new RegExp(`^${TICKER} `) })
    .click();

  await expect(page.getByLabel("Ticker", { exact: true })).toHaveValue(TICKER);
});
