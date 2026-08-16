"use client";

import { useEffect, useRef, useState } from "react";
import type { ConnectionStatus, Direction, PriceUpdate } from "@/lib/types";

const MAX_HISTORY = 180;

export interface PriceStreamState {
  prices: Record<string, PriceUpdate>;
  /** Price points accumulated from the stream since page load (PLAN §2). */
  history: Record<string, number[]>;
  status: ConnectionStatus;
}

function coerce(raw: Record<string, unknown>, fallbackTicker?: string): PriceUpdate | null {
  const ticker = String(raw.ticker ?? fallbackTicker ?? "");
  const price = raw.price;
  if (!ticker || typeof price !== "number" || !Number.isFinite(price)) return null;

  const previous = typeof raw.previous_price === "number" ? raw.previous_price : price;
  const direction: Direction =
    raw.direction === "up" || raw.direction === "down" || raw.direction === "flat"
      ? raw.direction
      : price > previous
        ? "up"
        : price < previous
          ? "down"
          : "flat";

  return {
    ticker,
    price,
    previous_price: previous,
    timestamp: typeof raw.timestamp === "number" ? raw.timestamp : Date.now() / 1000,
    change: typeof raw.change === "number" ? raw.change : price - previous,
    change_percent:
      typeof raw.change_percent === "number"
        ? raw.change_percent
        : previous
          ? ((price - previous) / previous) * 100
          : 0,
    direction,
  };
}

/**
 * The stream sends one event per tick carrying every tracked ticker as
 * `{"AAPL": {...}, "MSFT": {...}}`. A single bare update is also accepted so a
 * shape change on the backend degrades rather than breaks.
 */
export function parsePriceEvent(data: string): PriceUpdate[] {
  let payload: unknown;
  try {
    payload = JSON.parse(data);
  } catch {
    return [];
  }
  if (!payload || typeof payload !== "object") return [];

  const obj = payload as Record<string, unknown>;
  if (typeof obj.ticker === "string") {
    const single = coerce(obj);
    return single ? [single] : [];
  }

  const updates: PriceUpdate[] = [];
  for (const [ticker, value] of Object.entries(obj)) {
    if (value && typeof value === "object") {
      const update = coerce(value as Record<string, unknown>, ticker);
      if (update) updates.push(update);
    }
  }
  return updates;
}

export function usePriceStream(): PriceStreamState {
  const [prices, setPrices] = useState<Record<string, PriceUpdate>>({});
  const [history, setHistory] = useState<Record<string, number[]>>({});
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const everConnected = useRef(false);

  useEffect(() => {
    if (typeof EventSource === "undefined") {
      setStatus("disconnected");
      return;
    }

    const source = new EventSource("/api/stream/prices");

    source.onopen = () => {
      everConnected.current = true;
      setStatus("connected");
    };

    source.onmessage = (event: MessageEvent<string>) => {
      const updates = parsePriceEvent(event.data);
      if (updates.length === 0) return;

      setPrices((current) => {
        const next = { ...current };
        for (const update of updates) next[update.ticker] = update;
        return next;
      });

      setHistory((current) => {
        const next = { ...current };
        for (const update of updates) {
          const series = next[update.ticker] ?? [];
          next[update.ticker] =
            series.length >= MAX_HISTORY
              ? [...series.slice(series.length - MAX_HISTORY + 1), update.price]
              : [...series, update.price];
        }
        return next;
      });
    };

    source.onerror = () => {
      // EventSource retries on its own; CONNECTING means a retry is in flight.
      setStatus(
        source.readyState === EventSource.CLOSED
          ? "disconnected"
          : everConnected.current
            ? "reconnecting"
            : "connecting",
      );
    };

    return () => source.close();
  }, []);

  return { prices, history, status };
}
