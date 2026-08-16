"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import * as api from "@/lib/api";
import type { Portfolio, Position, PriceUpdate, Side, Snapshot, WatchlistItem } from "@/lib/types";

const EMPTY_PORTFOLIO: Portfolio = { cash_balance: 0, positions: [], total_value: 0 };

/**
 * Overlays streaming prices onto the last portfolio snapshot so P&L and total
 * value tick with the market instead of only refreshing after a trade.
 */
export function livePositions(
  positions: Position[],
  prices: Record<string, PriceUpdate>,
): Position[] {
  return positions.map((position) => {
    const live = prices[position.ticker]?.price;
    if (live === undefined) return position;
    const costBasis = position.quantity * position.avg_cost;
    const pnl = position.quantity * live - costBasis;
    return {
      ...position,
      current_price: live,
      unrealized_pnl: pnl,
      unrealized_pnl_percent: costBasis > 0 ? (pnl / costBasis) * 100 : 0,
      stale: false,
    };
  });
}

export function useTerminal(prices: Record<string, PriceUpdate>) {
  const [portfolio, setPortfolio] = useState<Portfolio>(EMPTY_PORTFOLIO);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [history, setHistory] = useState<Snapshot[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [portfolioResult, watchlistResult, historyResult] = await Promise.allSettled([
      api.fetchPortfolio(),
      api.fetchWatchlist(),
      api.fetchHistory(),
    ]);
    if (portfolioResult.status === "fulfilled") setPortfolio(portfolioResult.value);
    if (watchlistResult.status === "fulfilled") setWatchlist(watchlistResult.value);
    if (historyResult.status === "fulfilled") setHistory(historyResult.value);
  }, []);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 15_000);
    return () => clearInterval(timer);
  }, [refresh]);

  const run = useCallback(
    async (action: () => Promise<unknown>) => {
      setError(null);
      try {
        await action();
        await refresh();
        return true;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Something went wrong.");
        return false;
      }
    },
    [refresh],
  );

  const positions = useMemo(
    () => livePositions(portfolio.positions, prices),
    [portfolio.positions, prices],
  );

  const positionsValue = useMemo(
    () => positions.reduce((sum, p) => sum + p.quantity * p.current_price, 0),
    [positions],
  );

  return {
    cash: portfolio.cash_balance,
    positions,
    positionsValue,
    totalValue: portfolio.cash_balance + positionsValue,
    unrealizedPnl: positions.reduce((sum, p) => sum + p.unrealized_pnl, 0),
    watchlist,
    history,
    error,
    dismissError: () => setError(null),
    refresh,
    addTicker: (ticker: string) => run(() => api.addTicker(ticker)),
    removeTicker: (ticker: string) => run(() => api.removeTicker(ticker)),
    trade: (ticker: string, qty: number, side: Side) => run(() => api.executeTrade(ticker, qty, side)),
  };
}
