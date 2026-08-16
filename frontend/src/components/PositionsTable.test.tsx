import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PositionsTable } from "./PositionsTable";
import { livePositions } from "@/hooks/useTerminal";
import type { Position, PriceUpdate } from "@/lib/types";

const positions: Position[] = [
  {
    ticker: "AAPL",
    quantity: 10,
    avg_cost: 190,
    current_price: 202,
    unrealized_pnl: 120,
    unrealized_pnl_percent: 6.3158,
    stale: false,
  },
  {
    ticker: "TSLA",
    quantity: 5,
    avg_cost: 250,
    current_price: 240,
    unrealized_pnl: -50,
    unrealized_pnl_percent: -4,
    stale: false,
  },
];

describe("PositionsTable", () => {
  it("shows market value, P&L and percent change per position", () => {
    render(<PositionsTable positions={positions} selected={null} onSelect={vi.fn()} />);

    const winner = screen.getByText("AAPL").closest("tr")!;
    expect(within(winner).getByText("$2,020.00")).toBeInTheDocument();
    expect(within(winner).getByText(/\+\$120\.00/)).toBeInTheDocument();
    expect(within(winner).getByText(/6\.32%/)).toBeInTheDocument();

    const loser = screen.getByText("TSLA").closest("tr")!;
    expect(within(loser).getByText("$1,200.00")).toBeInTheDocument();
    expect(within(loser).getByText(/^−\$50\.00$/)).toBeInTheDocument();
  });

  it("colors gains green and losses red", () => {
    render(<PositionsTable positions={positions} selected={null} onSelect={vi.fn()} />);

    expect(screen.getByText(/\+\$120\.00/)).toHaveClass("text-up");
    expect(screen.getByText(/4\.00%/)).toHaveClass("text-down");
  });

  it("selects a ticker when a row is clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<PositionsTable positions={positions} selected={null} onSelect={onSelect} />);

    await user.click(screen.getByText("TSLA"));
    expect(onSelect).toHaveBeenCalledWith("TSLA");
  });

  it("reports an empty book plainly", () => {
    render(<PositionsTable positions={[]} selected={null} onSelect={vi.fn()} />);
    expect(screen.getByText("No open positions.")).toBeInTheDocument();
  });
});

describe("livePositions", () => {
  const prices: Record<string, PriceUpdate> = {
    AAPL: {
      ticker: "AAPL",
      price: 200,
      previous_price: 199,
      timestamp: 1,
      change: 1,
      change_percent: 0.5,
      direction: "up",
    },
  };

  it("recomputes P&L from the streaming price", () => {
    const [aapl] = livePositions([positions[0]], prices);
    expect(aapl.current_price).toBe(200);
    expect(aapl.unrealized_pnl).toBeCloseTo(100);
    expect(aapl.unrealized_pnl_percent).toBeCloseTo(5.2632, 3);
  });

  it("leaves positions with no live price untouched", () => {
    const [tsla] = livePositions([positions[1]], prices);
    expect(tsla).toEqual(positions[1]);
  });

  it("reports a loss when the price is below average cost", () => {
    const [aapl] = livePositions(
      [{ ...positions[0], avg_cost: 210 }],
      prices,
    );
    expect(aapl.unrealized_pnl).toBeCloseTo(-100);
    expect(aapl.unrealized_pnl_percent).toBeLessThan(0);
  });

  it("clears stale when a live price overlays the position", () => {
    const [aapl] = livePositions([{ ...positions[0], stale: true }], prices);
    expect(aapl.stale).toBe(false);
  });

  it("leaves stale untouched when no live price is available", () => {
    const [tsla] = livePositions([{ ...positions[1], stale: true }], prices);
    expect(tsla.stale).toBe(true);
  });
});
