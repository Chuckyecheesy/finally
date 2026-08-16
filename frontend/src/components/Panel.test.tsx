import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Panel } from "./Panel";

describe("Panel", () => {
  it("renders the title as a heading and labels the outer section", () => {
    render(
      <Panel title="Watchlist">
        <div>body</div>
      </Panel>,
    );

    expect(screen.getByRole("heading", { name: "Watchlist" })).toBeInTheDocument();
    expect(screen.getByLabelText("Watchlist").tagName).toBe("SECTION");
  });

  it("renders children inside the body", () => {
    render(
      <Panel title="Watchlist">
        <div>Panel Body Content</div>
      </Panel>,
    );

    expect(screen.getByText("Panel Body Content")).toBeInTheDocument();
  });

  it("renders the aside slot when provided", () => {
    render(
      <Panel title="Watchlist" aside={<span>Extra</span>}>
        <div>body</div>
      </Panel>,
    );

    expect(screen.getByText("Extra")).toBeInTheDocument();
  });

  it("omits aside content when not passed", () => {
    render(
      <Panel title="Watchlist">
        <div>body</div>
      </Panel>,
    );

    expect(screen.queryByText("Extra")).not.toBeInTheDocument();
  });

  it("applies bodyClassName to the body wrapper", () => {
    render(
      <Panel title="Watchlist" bodyClassName="custom-body">
        <div>Panel Body Content</div>
      </Panel>,
    );

    const body = screen.getByText("Panel Body Content").parentElement;
    expect(body?.className).toContain("custom-body");
  });
});
