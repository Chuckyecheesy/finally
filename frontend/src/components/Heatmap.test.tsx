import { cloneElement, isValidElement, type ReactElement, type ReactNode } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("recharts", async (importOriginal) => {
  const actual = await importOriginal<typeof import("recharts")>();
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: ReactNode }) => (
      <div style={{ width: 600, height: 400 }}>
        {isValidElement(children)
          ? cloneElement(children as ReactElement<{ width?: number; height?: number }>, {
              width: 600,
              height: 400,
            })
          : children}
      </div>
    ),
  };
});

import { Heatmap } from "./Heatmap";
import type { Position } from "@/lib/types";

function makePosition(overrides: Partial<Position> = {}): Position {
  return {
    ticker: "AAPL",
    quantity: 10,
    avg_cost: 190,
    current_price: 202,
    unrealized_pnl: 120,
    unrealized_pnl_percent: 6.3158,
    stale: false,
    ...overrides,
  };
}

describe("Heatmap", () => {
  it("shows an empty-state message when there are no positions", () => {
    render(<Heatmap positions={[]} onSelect={vi.fn()} />);
    expect(
      screen.getByText("Buy a position and it appears here, sized by weight."),
    ).toBeInTheDocument();
  });

  it("shows the empty-state message when all positions are filtered out", () => {
    const positions = [
      makePosition({ ticker: "AAPL", quantity: 0 }),
      makePosition({ ticker: "TSLA", current_price: 0 }),
    ];
    render(<Heatmap positions={positions} onSelect={vi.fn()} />);
    expect(
      screen.getByText("Buy a position and it appears here, sized by weight."),
    ).toBeInTheDocument();
  });

  it("renders treemap cells for valid positions", () => {
    const positions = [
      makePosition({ ticker: "AAPL", quantity: 10, current_price: 202 }),
      makePosition({ ticker: "TSLA", quantity: 5, current_price: 240, unrealized_pnl_percent: -4 }),
    ];
    render(<Heatmap positions={positions} onSelect={vi.fn()} />);

    const items = screen.getAllByRole("listitem");
    expect(items.length).toBeGreaterThan(0);
    expect(items.some((el) => el.getAttribute("aria-label")?.startsWith("AAPL"))).toBe(true);
  });

  it("calls onSelect with the clicked ticker", () => {
    const onSelect = vi.fn();
    const positions = [
      makePosition({ ticker: "AAPL", quantity: 10, current_price: 202 }),
      makePosition({ ticker: "TSLA", quantity: 5, current_price: 240, unrealized_pnl_percent: -4 }),
    ];
    render(<Heatmap positions={positions} onSelect={onSelect} />);

    const items = screen.getAllByRole("listitem");
    const aaplItem = items.find((el) => el.getAttribute("aria-label")?.startsWith("AAPL"));
    expect(aaplItem).toBeDefined();
    fireEvent.click(aaplItem!);
    expect(onSelect).toHaveBeenCalledWith("AAPL");
  });
});
