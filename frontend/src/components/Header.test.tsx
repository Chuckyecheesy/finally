import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Header } from "./Header";
import type { ConnectionStatus } from "@/lib/types";

const base = {
  totalValue: 10450.5,
  cash: 8550.5,
  unrealizedPnl: 100,
  unrealizedPnlPercent: 5.5555,
  status: "connected" as ConnectionStatus,
};

describe("Header", () => {
  it("shows total value, cash, and signed unrealized P&L", () => {
    render(<Header {...base} />);
    expect(screen.getByText("$10,450.50")).toBeInTheDocument();
    expect(screen.getByText("$8,550.50")).toBeInTheDocument();
    expect(screen.getByText(/\+\$100\.00\s+\+5\.56%/)).toBeInTheDocument();
  });

  it("renders a loss in the down color", () => {
    render(<Header {...base} unrealizedPnl={-250} unrealizedPnlPercent={-3.2} />);
    expect(screen.getByText(/−\$250\.00/)).toHaveClass("text-down");
  });

  it.each([
    ["connected", "Live"],
    ["connecting", "Connecting"],
    ["reconnecting", "Reconnecting"],
    ["disconnected", "Offline"],
  ] as const)("reflects the %s stream state", (status, label) => {
    render(<Header {...base} status={status} />);
    expect(screen.getByTestId("connection-dot")).toHaveAttribute("data-status", status);
    expect(screen.getByRole("status")).toHaveTextContent(label);
  });
});
