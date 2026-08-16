import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TradeBar } from "./TradeBar";
import type { Side } from "@/lib/types";

function setup(overrides: Partial<Parameters<typeof TradeBar>[0]> = {}) {
  const props = {
    ticker: "AAPL",
    lastPrice: 190,
    cash: 10000,
    onTrade: vi.fn(),
    error: null,
    onDismissError: vi.fn(),
    ...overrides,
  };
  const utils = render(<TradeBar {...props} />);
  return { ...utils, props };
}

describe("TradeBar", () => {
  it("prefills the ticker input from the ticker prop", () => {
    setup({ ticker: "AAPL" });
    expect(screen.getByLabelText("Ticker")).toHaveValue("AAPL");
  });

  it("disables Buy and Sell when quantity is zero", async () => {
    const user = userEvent.setup();
    setup();

    await user.clear(screen.getByLabelText("Quantity"));
    await user.type(screen.getByLabelText("Quantity"), "0");

    expect(screen.getByRole("button", { name: "Buy" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Sell" })).toBeDisabled();
  });

  it("disables Buy and Sell when quantity is non-numeric", async () => {
    const user = userEvent.setup();
    setup();

    await user.clear(screen.getByLabelText("Quantity"));
    await user.type(screen.getByLabelText("Quantity"), "abc");

    expect(screen.getByRole("button", { name: "Buy" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Sell" })).toBeDisabled();
  });

  it("enables Buy and Sell with a valid symbol and positive quantity", () => {
    setup({ ticker: "AAPL" });

    expect(screen.getByRole("button", { name: "Buy" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Sell" })).toBeEnabled();
  });

  it("calls onTrade with normalized args on Buy", async () => {
    const user = userEvent.setup();
    const onTrade = vi.fn();
    setup({ ticker: "aapl", onTrade });

    await user.clear(screen.getByLabelText("Quantity"));
    await user.type(screen.getByLabelText("Quantity"), "5");
    await user.click(screen.getByRole("button", { name: "Buy" }));

    expect(onTrade).toHaveBeenCalledWith("AAPL", 5, "buy" as Side);
  });

  it("calls onTrade with side 'sell' when clicking Sell", async () => {
    const user = userEvent.setup();
    const onTrade = vi.fn();
    setup({ ticker: "AAPL", onTrade });

    await user.clear(screen.getByLabelText("Quantity"));
    await user.type(screen.getByLabelText("Quantity"), "5");
    await user.click(screen.getByRole("button", { name: "Sell" }));

    expect(onTrade).toHaveBeenCalledWith("AAPL", 5, "sell" as Side);
  });

  it("displays the estimated cost when quantity and lastPrice are valid", () => {
    setup({ ticker: "AAPL", lastPrice: 190 });
    expect(screen.getByText("$190.00")).toBeInTheDocument();
  });

  it("shows a dash for estimated cost when lastPrice is null", () => {
    setup({ ticker: "AAPL", lastPrice: null });
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("displays the cash balance formatted as money", () => {
    setup({ cash: 10000 });
    expect(screen.getByText("$10,000.00")).toBeInTheDocument();
  });

  it("renders an alert with the error text and dismisses it", async () => {
    const user = userEvent.setup();
    const onDismissError = vi.fn();
    setup({ error: "Insufficient cash", onDismissError });

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Insufficient cash");

    await user.click(screen.getByRole("button", { name: "Dismiss error" }));
    expect(onDismissError).toHaveBeenCalled();
  });

  it("renders no alert when error is null", () => {
    setup({ error: null });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("updates the ticker input value when the ticker prop changes", () => {
    const { rerender, props } = setup({ ticker: "AAPL" });
    rerender(<TradeBar {...props} ticker="TSLA" />);
    expect(screen.getByLabelText("Ticker")).toHaveValue("TSLA");
  });
});
