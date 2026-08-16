import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Watchlist } from "./Watchlist";
import type { PriceUpdate, WatchlistItem } from "@/lib/types";

const items: WatchlistItem[] = [
  { ticker: "AAPL", price: 190 },
  { ticker: "MSFT", price: 420 },
];

const prices: Record<string, PriceUpdate> = {
  AAPL: {
    ticker: "AAPL",
    price: 191.5,
    previous_price: 190,
    timestamp: 1,
    change: 1.5,
    change_percent: 0.79,
    direction: "up",
  },
};

function setup(overrides: Partial<Parameters<typeof Watchlist>[0]> = {}) {
  const props = {
    items,
    prices,
    history: { AAPL: [190, 190.8, 191.5] },
    selected: null,
    onSelect: vi.fn(),
    onAdd: vi.fn(),
    onRemove: vi.fn(),
    ...overrides,
  };
  render(<Watchlist {...props} />);
  return props;
}

describe("Watchlist", () => {
  it("renders each ticker with its streaming price", () => {
    setup();
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("191.50")).toBeInTheDocument();
  });

  it("shows change since page load, computed from the accumulated ticks", () => {
    setup();
    // 190 → 191.50 across the session history is +0.79%.
    expect(screen.getByText(/\+0\.79%/)).toHaveClass("text-up");
  });

  it("shows no change until a second tick arrives", () => {
    setup({ history: { AAPL: [190] } });
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("falls back to the fetched price before any tick arrives", () => {
    setup();
    expect(screen.getByText("420.00")).toBeInTheDocument();
  });

  it("adds a ticker, normalizing case, and clears the input", async () => {
    const user = userEvent.setup();
    const { onAdd } = setup();

    const input = screen.getByLabelText("Add ticker");
    await user.type(input, "pypl");
    await user.click(screen.getByRole("button", { name: "+" }));

    expect(onAdd).toHaveBeenCalledWith("PYPL");
    expect(input).toHaveValue("");
  });

  it("ignores an empty add", async () => {
    const user = userEvent.setup();
    const { onAdd } = setup();
    await user.click(screen.getByRole("button", { name: "+" }));
    expect(onAdd).not.toHaveBeenCalled();
  });

  it("removes a ticker without selecting it", async () => {
    const user = userEvent.setup();
    const { onRemove, onSelect } = setup();

    await user.click(screen.getByRole("button", { name: "Remove MSFT from watchlist" }));

    expect(onRemove).toHaveBeenCalledWith("MSFT");
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("selects a ticker when its row is clicked", async () => {
    const user = userEvent.setup();
    const { onSelect } = setup();
    await user.click(screen.getByText("AAPL"));
    expect(onSelect).toHaveBeenCalledWith("AAPL");
  });

  it("marks the tick rail with the direction of the last update", () => {
    setup();
    expect(screen.getByTestId("tick-rail-AAPL")).toHaveClass("rail-up");
    expect(screen.getByTestId("tick-rail-MSFT").className).not.toMatch(/rail-/);
  });

  it("invites a first ticker when the list is empty", () => {
    setup({ items: [] });
    expect(screen.getByText(/No tickers yet/)).toBeInTheDocument();
  });
});
