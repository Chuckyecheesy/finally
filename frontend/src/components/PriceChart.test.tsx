import { cloneElement, isValidElement, type ReactElement, type ReactNode } from "react";
import { render, screen } from "@testing-library/react";
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

import { PriceChart } from "./PriceChart";
import type { PriceUpdate } from "@/lib/types";

function makeUpdate(overrides: Partial<PriceUpdate> = {}): PriceUpdate {
  return {
    ticker: "AAPL",
    price: 105,
    previous_price: 104,
    timestamp: 1,
    change: 1,
    change_percent: 0.96,
    direction: "up",
    ...overrides,
  };
}

describe("PriceChart", () => {
  it("prompts to select a ticker when none is selected and no points exist", () => {
    render(<PriceChart ticker={null} points={[]} />);
    expect(screen.getByText("Select a ticker from the watchlist.")).toBeInTheDocument();
  });

  it("shows a collecting-ticks message with fewer than 2 points and a selected ticker", () => {
    render(<PriceChart ticker="AAPL" points={[100]} />);
    expect(
      screen.getByText("Collecting ticks — the chart draws as prices stream in."),
    ).toBeInTheDocument();
    expect(screen.getByText("AAPL · Session")).toBeInTheDocument();
  });

  it("renders no price/percent aside content when no update is provided", () => {
    render(<PriceChart ticker={null} points={[]} />);
    expect(screen.queryByText(/^\d+\.\d{2}$/)).not.toBeInTheDocument();
  });

  it("shows the formatted price and a positive session-change percent when rising", () => {
    const update = makeUpdate({ price: 105 });
    const { container } = render(
      <PriceChart ticker="AAPL" points={[100, 102, 101, 105]} update={update} />,
    );

    const header = container.querySelector("header")!;
    expect(header).toHaveTextContent("105.00");
    const pct = header.querySelector(".tnum:last-child")!;
    expect(pct).toHaveTextContent("+5.00%");
    expect(pct).toHaveClass("text-up");
  });

  it("shows a negative session-change percent when falling", () => {
    const update = makeUpdate({ price: 95 });
    const { container } = render(<PriceChart ticker="AAPL" points={[100, 95]} update={update} />);

    const header = container.querySelector("header")!;
    expect(header).toHaveTextContent("95.00");
    const pct = header.querySelector(".tnum:last-child")!;
    expect(pct).toHaveTextContent("−5.00%");
    expect(pct).toHaveClass("text-down");
  });
});
