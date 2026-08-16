import { expect, test } from "@playwright/test";
import {
  actionChips,
  assistantMessages,
  cashBalance,
  chatPanel,
  openApp,
  positionRow,
  sendChat,
  waitForStreamingPrice,
  watchlistRow,
} from "./helpers";

// Trigger phrases come from backend/app/llm/mock.py's module docstring.
test.describe.configure({ mode: "serial" });

test("assistant answers a portfolio question", async ({ page }) => {
  await openApp(page);

  await sendChat(page, "how is my portfolio doing?");

  await expect(assistantMessages(page)).toHaveCount(1);
  await expect(assistantMessages(page).first()).toContainText("Here's your portfolio:");
  await expect(actionChips(page)).toHaveCount(0);
});

test("assistant executes a trade and the portfolio updates", async ({ page }) => {
  await openApp(page);
  await waitForStreamingPrice(page, "AAPL");

  const cashBefore = await cashBalance(page);
  await expect(positionRow(page, "AAPL")).toHaveCount(0);

  await sendChat(page, "buy 5 shares of AAPL");

  // 1. The reply and its inline fill confirmation.
  await expect(assistantMessages(page).last()).not.toBeEmpty();
  const chip = actionChips(page).last();
  await expect(chip).toContainText(/BUY 5 AAPL @ \d+\.\d{2}/);

  // 2. The trade really happened: position opened and cash debited.
  await expect(positionRow(page, "AAPL")).toHaveCount(1);
  await expect(positionRow(page, "AAPL").locator("td").nth(1)).toHaveText("5");
  await expect.poll(async () => cashBalance(page)).toBeLessThan(cashBefore);
});

test("assistant sells and the position shrinks", async ({ page }) => {
  await openApp(page);
  await waitForStreamingPrice(page, "AAPL");
  await expect(positionRow(page, "AAPL")).toHaveCount(1);

  const cashBefore = await cashBalance(page);
  await sendChat(page, "sell 2.5 AAPL");

  await expect(actionChips(page).last()).toContainText(/SELL 2.5 AAPL @ \d+\.\d{2}/);
  await expect(positionRow(page, "AAPL").locator("td").nth(1)).toHaveText("2.5");
  await expect.poll(async () => cashBalance(page)).toBeGreaterThan(cashBefore);
});

test("assistant manages the watchlist", async ({ page }) => {
  await openApp(page);
  await expect(watchlistRow(page, "SHOP")).toHaveCount(0);

  await sendChat(page, "watch SHOP");
  await expect(actionChips(page).last()).toContainText("Added SHOP");
  await expect(watchlistRow(page, "SHOP")).toHaveCount(1);

  await sendChat(page, "unwatch SHOP");
  await expect(actionChips(page).last()).toContainText("Removed SHOP");
  await expect(watchlistRow(page, "SHOP")).toHaveCount(0);
});

test("a rejected trade is reported inline without moving cash", async ({ page }) => {
  await openApp(page);
  await waitForStreamingPrice(page, "META");

  const cashBefore = await cashBalance(page);
  await sendChat(page, "buy 99999 META");

  await expect(actionChips(page).last()).toContainText(/BUY 99999 META — /);
  await expect(positionRow(page, "META")).toHaveCount(0);
  expect(await cashBalance(page)).toBe(cashBefore);
});

test("the chat panel collapses and reopens", async ({ page }) => {
  await openApp(page);

  await chatPanel(page).getByRole("button", { name: "Collapse AI assistant" }).click();
  await expect(chatPanel(page)).toHaveCount(0);

  await page.getByRole("button", { name: "Open AI assistant" }).click();
  await expect(chatPanel(page)).toBeVisible();
});
