import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useTerminal } from "./useTerminal";
import * as api from "@/lib/api";
import type { Portfolio, Snapshot, WatchlistItem } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  fetchPortfolio: vi.fn(),
  fetchWatchlist: vi.fn(),
  fetchHistory: vi.fn(),
  addTicker: vi.fn(),
  removeTicker: vi.fn(),
  executeTrade: vi.fn(),
}));

const EMPTY_PORTFOLIO: Portfolio = { cash_balance: 0, positions: [], total_value: 0 };
const EMPTY_WATCHLIST: WatchlistItem[] = [];
const EMPTY_HISTORY: Snapshot[] = [];

function setVisibility(state: "visible" | "hidden") {
  Object.defineProperty(document, "visibilityState", { value: state, configurable: true });
  document.dispatchEvent(new Event("visibilitychange"));
}

describe("useTerminal polling", () => {
  beforeEach(() => {
    vi.mocked(api.fetchPortfolio).mockResolvedValue(EMPTY_PORTFOLIO);
    vi.mocked(api.fetchWatchlist).mockResolvedValue(EMPTY_WATCHLIST);
    vi.mocked(api.fetchHistory).mockResolvedValue(EMPTY_HISTORY);
    vi.useFakeTimers();
    setVisibility("visible");
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("polls every 15s while the tab stays visible", async () => {
    renderHook(() => useTerminal({}));

    expect(api.fetchPortfolio).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15_000);
    });

    expect(api.fetchPortfolio).toHaveBeenCalledTimes(2);
  });

  it("stops polling when the tab is backgrounded", async () => {
    renderHook(() => useTerminal({}));
    expect(api.fetchPortfolio).toHaveBeenCalledTimes(1);

    await act(async () => {
      setVisibility("hidden");
    });

    const callsAtHide = vi.mocked(api.fetchPortfolio).mock.calls.length;

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });

    expect(api.fetchPortfolio).toHaveBeenCalledTimes(callsAtHide);
  });

  it("resumes polling, with an immediate refresh, when the tab is foregrounded again", async () => {
    renderHook(() => useTerminal({}));
    expect(api.fetchPortfolio).toHaveBeenCalledTimes(1);

    await act(async () => {
      setVisibility("hidden");
    });

    const callsAtHide = vi.mocked(api.fetchPortfolio).mock.calls.length;

    await act(async () => {
      setVisibility("visible");
    });

    expect(api.fetchPortfolio).toHaveBeenCalledTimes(callsAtHide + 1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15_000);
    });

    expect(api.fetchPortfolio).toHaveBeenCalledTimes(callsAtHide + 2);
  });
});
