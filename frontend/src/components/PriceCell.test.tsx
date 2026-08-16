import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PriceCell } from "./PriceCell";

describe("PriceCell", () => {
  it("does not flash on first render", () => {
    render(<PriceCell value={190.5} />);
    const cell = screen.getByTestId("price-cell");
    expect(cell).toHaveTextContent("190.50");
    expect(cell.className).not.toMatch(/flash-/);
  });

  it("flashes green when the price ticks up", () => {
    const { rerender } = render(<PriceCell value={190.5} />);
    rerender(<PriceCell value={191.25} />);

    const cell = screen.getByTestId("price-cell");
    expect(cell).toHaveTextContent("191.25");
    expect(cell).toHaveClass("flash-up");
  });

  it("flashes red when the price ticks down", () => {
    const { rerender } = render(<PriceCell value={190.5} />);
    rerender(<PriceCell value={189.1} />);

    expect(screen.getByTestId("price-cell")).toHaveClass("flash-down");
  });

  it("restarts the animation on each successive tick", () => {
    const { rerender } = render(<PriceCell value={100} />);
    rerender(<PriceCell value={101} />);
    const first = screen.getByTestId("price-cell");

    rerender(<PriceCell value={102} />);
    const second = screen.getByTestId("price-cell");

    // A fresh node means the CSS animation replays rather than sitting finished.
    expect(second).not.toBe(first);
    expect(second).toHaveClass("flash-up");
  });

  it("does not flash when the price is unchanged", () => {
    const { rerender } = render(<PriceCell value={100} />);
    rerender(<PriceCell value={100} />);
    expect(screen.getByTestId("price-cell").className).not.toMatch(/flash-/);
  });

  it("renders a placeholder when there is no price yet", () => {
    render(<PriceCell value={null} />);
    expect(screen.getByTestId("price-cell")).toHaveTextContent("—");
  });
});
