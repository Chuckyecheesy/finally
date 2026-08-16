import { expect, type Page } from "@playwright/test";

export const DEFAULT_WATCHLIST = [
  "AAPL",
  "GOOGL",
  "MSFT",
  "AMZN",
  "TSLA",
  "NVDA",
  "META",
  "JPM",
  "V",
  "NFLX",
];

/** "$10,000.00" / "−$1,234.56" -> 10000 / -1234.56 */
export function parseMoney(text: string): number {
  const negative = text.includes("−") || text.includes("-") || text.trim().startsWith("(");
  const digits = text.replace(/[^0-9.]/g, "");
  const value = Number.parseFloat(digits);
  if (!Number.isFinite(value)) throw new Error(`Not a money string: ${JSON.stringify(text)}`);
  return negative ? -value : value;
}

function headerStat(page: Page, label: string) {
  return page
    .locator("header")
    .first()
    .locator("div")
    .filter({ has: page.getByText(label, { exact: true }) })
    .locator("span.tnum")
    .first();
}

export async function cashBalance(page: Page): Promise<number> {
  return parseMoney(await headerStat(page, "Cash").innerText());
}

export async function totalValue(page: Page): Promise<number> {
  return parseMoney(await headerStat(page, "Total Value").innerText());
}

// Every Panel renders <section aria-label={title}>, i.e. a named ARIA region.
export const watchlistPanel = (page: Page) => page.getByRole("region", { name: "Watchlist" });
export const positionsPanel = (page: Page) => page.getByRole("region", { name: "Positions" });
export const allocationPanel = (page: Page) => page.getByRole("region", { name: "Allocation" });
export const pnlPanel = (page: Page) => page.getByRole("region", { name: "Portfolio Value" });
export const chatPanel = (page: Page) => page.getByRole("region", { name: "AI assistant" });

/** Row in the positions table for a ticker, or a zero-count locator if flat. */
export const positionRow = (page: Page, ticker: string) =>
  positionsPanel(page).locator("tbody tr").filter({ has: page.getByText(ticker, { exact: true }) });

export const watchlistRow = (page: Page, ticker: string) =>
  watchlistPanel(page).locator("li").filter({ has: page.getByText(ticker, { exact: true }) });

/**
 * Waits until the SSE stream has pushed a price for `ticker`, i.e. the ticker's
 * price cell is a number rather than the "—" placeholder.
 */
export async function waitForStreamingPrice(page: Page, ticker: string): Promise<number> {
  const cell = watchlistRow(page, ticker).getByTestId("price-cell");
  await expect(cell).not.toHaveText("—", { timeout: 30_000 });
  return Number.parseFloat(await cell.innerText());
}

export async function waitForConnected(page: Page): Promise<void> {
  await expect(page.getByTestId("connection-dot")).toHaveAttribute("data-status", "connected", {
    timeout: 30_000,
  });
}

/** The row's own button; the second button in a row is "Remove …". */
export const selectTicker = (page: Page, ticker: string) =>
  watchlistRow(page, ticker).getByRole("button").first().click();

// The Buy/Sell labels are uppercased by CSS, so match case-insensitively.
const tradeButton = (page: Page, side: "buy" | "sell") =>
  page.getByRole("button", { name: new RegExp(`^${side}$`, "i") });

/** Places a market order through the trade bar and waits for the refresh. */
export async function trade(
  page: Page,
  ticker: string,
  qty: number,
  side: "buy" | "sell",
): Promise<void> {
  await page.getByLabel("Ticker", { exact: true }).fill(ticker);
  await page.getByLabel("Quantity").fill(String(qty));
  const response = page.waitForResponse(
    (res) => res.url().includes("/api/portfolio/trade") && res.request().method() === "POST",
  );
  await tradeButton(page, side).click();
  await response;
  // The trade bar re-enables its buttons only after the portfolio refresh lands.
  await expect(tradeButton(page, side)).toBeEnabled();
}

export async function sendChat(page: Page, message: string): Promise<void> {
  await chatPanel(page).getByLabel("Message").fill(message);
  const response = page.waitForResponse(
    (res) => res.url().includes("/api/chat") && res.request().method() === "POST",
  );
  await chatPanel(page).getByRole("button", { name: "Send" }).click();
  await response;
  await expect(chatPanel(page).getByLabel("Message")).toBeEnabled();
}

/** Assistant reply bubbles, in order (user bubbles are not pre-wrapped). */
export const assistantMessages = (page: Page) =>
  chatPanel(page).locator("p.whitespace-pre-wrap");

/** Inline action confirmations (trade fills, watchlist changes) in the chat. */
export const actionChips = (page: Page) => chatPanel(page).locator("div.border-l-2");

export async function openApp(page: Page): Promise<void> {
  await page.goto("/");
  await waitForConnected(page);
  await expect(watchlistPanel(page).locator("li").first()).toBeVisible();
}
