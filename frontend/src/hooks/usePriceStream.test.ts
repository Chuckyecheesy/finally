import { describe, expect, it } from "vitest";
import { parsePriceEvent } from "./usePriceStream";

describe("parsePriceEvent", () => {
  it("reads the keyed map of every tracked ticker the backend sends", () => {
    const updates = parsePriceEvent(
      JSON.stringify({
        AAPL: {
          ticker: "AAPL",
          price: 191.2,
          previous_price: 190,
          timestamp: 1,
          change: 1.2,
          change_percent: 0.63,
          direction: "up",
        },
        TSLA: {
          ticker: "TSLA",
          price: 240,
          previous_price: 242,
          timestamp: 1,
          change: -2,
          change_percent: -0.83,
          direction: "down",
        },
      }),
    );

    expect(updates).toHaveLength(2);
    expect(updates.map((u) => u.ticker).sort()).toEqual(["AAPL", "TSLA"]);
    expect(updates.find((u) => u.ticker === "TSLA")?.direction).toBe("down");
  });

  it("accepts a single bare update", () => {
    const [update] = parsePriceEvent(
      JSON.stringify({ ticker: "MSFT", price: 421, previous_price: 420 }),
    );
    expect(update.ticker).toBe("MSFT");
    expect(update.direction).toBe("up");
  });

  it("derives direction and change when the backend omits them", () => {
    const [update] = parsePriceEvent(
      JSON.stringify({ AAPL: { ticker: "AAPL", price: 100, previous_price: 125 } }),
    );
    expect(update.direction).toBe("down");
    expect(update.change).toBeCloseTo(-25);
    expect(update.change_percent).toBeCloseTo(-20);
  });

  it("drops malformed entries instead of throwing", () => {
    expect(parsePriceEvent("not json")).toEqual([]);
    expect(parsePriceEvent(JSON.stringify({ AAPL: { ticker: "AAPL" } }))).toEqual([]);
    expect(parsePriceEvent(JSON.stringify({ AAPL: null }))).toEqual([]);
  });
});
