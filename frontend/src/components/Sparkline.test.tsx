import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Sparkline } from "./Sparkline";

describe("Sparkline", () => {
  it("renders a placeholder line when there are fewer than 2 points", () => {
    const { container } = render(<Sparkline points={[5]} />);
    const svg = container.querySelector("svg");

    expect(svg).toHaveClass("opacity-40");
    expect(container.querySelector("line")).toBeInTheDocument();
    expect(container.querySelector("polyline")).not.toBeInTheDocument();
  });

  it("renders a placeholder line when there are no points", () => {
    const { container } = render(<Sparkline points={[]} />);
    const svg = container.querySelector("svg");

    expect(svg).toHaveClass("opacity-40");
    expect(container.querySelector("line")).toBeInTheDocument();
    expect(container.querySelector("polyline")).not.toBeInTheDocument();
  });

  it("renders a rising polyline colored text-up when the last point is >= the first", () => {
    const { container } = render(<Sparkline points={[10, 12, 11, 15]} />);
    const svg = container.querySelector("svg");

    expect(container.querySelector("polyline")).toBeInTheDocument();
    expect(svg).toHaveClass("text-up");
  });

  it("renders a falling polyline colored text-down when the last point is < the first", () => {
    const { container } = render(<Sparkline points={[15, 12, 11, 10]} />);
    const svg = container.querySelector("svg");

    expect(container.querySelector("polyline")).toBeInTheDocument();
    expect(svg).toHaveClass("text-down");
  });

  it("respects custom width and height props", () => {
    const { container } = render(<Sparkline points={[10, 12]} width={100} height={30} />);
    const svg = container.querySelector("svg");

    expect(svg).toHaveAttribute("width", "100");
    expect(svg).toHaveAttribute("height", "30");
  });
});
