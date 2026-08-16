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

import { PnlChart } from "./PnlChart";
import type { Snapshot } from "@/lib/types";

function makeSnapshot(totalValue: number, recordedAt: string): Snapshot {
  return { total_value: totalValue, recorded_at: recordedAt };
}

describe("PnlChart", () => {
  it("shows the empty-state message with no snapshots", () => {
    render(<PnlChart snapshots={[]} />);
    expect(
      screen.getByText("Snapshots are recorded every 30 seconds and after each trade."),
    ).toBeInTheDocument();
  });

  it("shows the empty-state message with only one snapshot", () => {
    render(<PnlChart snapshots={[makeSnapshot(10000, "2024-01-01T09:30:00Z")]} />);
    expect(
      screen.getByText("Snapshots are recorded every 30 seconds and after each trade."),
    ).toBeInTheDocument();
  });

  it("renders a rising line color when the last value is >= the first", () => {
    const snapshots = [
      makeSnapshot(10000, "2024-01-01T09:30:00Z"),
      makeSnapshot(10500, "2024-01-01T09:31:00Z"),
    ];
    const { container } = render(<PnlChart snapshots={snapshots} />);
    const line = container.querySelector("path.recharts-line-curve");
    expect(line).not.toBeNull();
    expect(line).toHaveAttribute("stroke", "var(--color-primary)");
  });

  it("renders a falling line color when the last value is < the first", () => {
    const snapshots = [
      makeSnapshot(10500, "2024-01-01T09:30:00Z"),
      makeSnapshot(10000, "2024-01-01T09:31:00Z"),
    ];
    const { container } = render(<PnlChart snapshots={snapshots} />);
    const line = container.querySelector("path.recharts-line-curve");
    expect(line).not.toBeNull();
    expect(line).toHaveAttribute("stroke", "var(--color-down)");
  });
});
