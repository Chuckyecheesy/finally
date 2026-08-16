"use client";

import { useState, type FormEvent } from "react";
import { Panel } from "./Panel";
import { PriceCell } from "./PriceCell";
import { Sparkline } from "./Sparkline";
import { percent } from "@/lib/format";
import type { PriceUpdate, WatchlistItem } from "@/lib/types";

interface WatchlistProps {
  items: WatchlistItem[];
  prices: Record<string, PriceUpdate>;
  history: Record<string, number[]>;
  selected: string | null;
  onSelect: (ticker: string) => void;
  onAdd: (ticker: string) => void | Promise<unknown>;
  onRemove: (ticker: string) => void | Promise<unknown>;
}

export function Watchlist({
  items,
  prices,
  history,
  selected,
  onSelect,
  onAdd,
  onRemove,
}: WatchlistProps) {
  const [draft, setDraft] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    const ticker = draft.trim().toUpperCase();
    if (!ticker) return;
    void onAdd(ticker);
    setDraft("");
  }

  return (
    <Panel
      title="Watchlist"
      aside={<span className="tnum text-[10px] text-terminal-faint">{items.length}</span>}
      bodyClassName="flex flex-col"
    >
      <ul className="min-h-0 flex-1 overflow-y-auto">
        {items.map((item) => {
          const update = prices[item.ticker];
          const value = update?.price ?? item.price ?? null;
          const isSelected = selected === item.ticker;
          const points = history[item.ticker] ?? [];
          // Change since page load, matching what the sparkline draws. The
          // per-tick delta the stream carries is too small to be legible.
          const sessionChange =
            points.length >= 2 && points[0] !== 0
              ? ((points[points.length - 1] - points[0]) / points[0]) * 100
              : null;
          const railClass =
            update?.direction === "up"
              ? "rail-up"
              : update?.direction === "down"
                ? "rail-down"
                : "";

          return (
            <li key={item.ticker} className="group relative border-b border-terminal-line/60">
              {/* Tick rail — decays over ~1.4s so the column reads as activity heat. */}
              <span
                key={`${item.ticker}-${update?.timestamp ?? 0}`}
                aria-hidden
                data-testid={`tick-rail-${item.ticker}`}
                className={`absolute left-0 top-0 h-full w-[2px] ${railClass}`}
              />
              <button
                type="button"
                onClick={() => onSelect(item.ticker)}
                aria-current={isSelected}
                className={`flex w-full items-center gap-2 py-1.5 pl-3 pr-7 text-left transition-colors hover:bg-terminal-raised ${
                  isSelected ? "bg-terminal-raised" : ""
                }`}
              >
                <span
                  className={`w-12 shrink-0 font-mono text-[12px] font-bold tracking-tight ${
                    isSelected ? "text-accent" : "text-terminal-text"
                  }`}
                >
                  {item.ticker}
                </span>
                <Sparkline points={points} />
                <span className="ml-auto flex flex-col items-end">
                  <PriceCell value={value} className="text-[12px]" />
                  <span
                    className={`tnum px-1 text-[10px] ${
                      sessionChange === null || sessionChange === 0
                        ? "text-terminal-faint"
                        : sessionChange > 0
                          ? "text-up"
                          : "text-down"
                    }`}
                  >
                    {sessionChange === null ? "—" : percent(sessionChange)}
                  </span>
                </span>
              </button>
              <button
                type="button"
                onClick={() => void onRemove(item.ticker)}
                aria-label={`Remove ${item.ticker} from watchlist`}
                className="absolute right-1 top-1/2 -translate-y-1/2 px-1 text-[13px] leading-none text-terminal-faint opacity-0 transition hover:text-down focus-visible:opacity-100 group-hover:opacity-100"
              >
                ×
              </button>
            </li>
          );
        })}
        {items.length === 0 && (
          <li className="px-3 py-6 text-center text-[11px] text-terminal-dim">
            No tickers yet. Add one below to start streaming prices.
          </li>
        )}
      </ul>

      <form onSubmit={submit} className="flex shrink-0 border-t border-terminal-line">
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="ADD TICKER"
          aria-label="Add ticker"
          maxLength={12}
          className="min-w-0 flex-1 bg-transparent px-3 py-2 font-mono text-[11px] uppercase tracking-wider text-terminal-text placeholder:text-terminal-faint focus:outline-none"
        />
        <button
          type="submit"
          className="border-l border-terminal-line px-3 text-[11px] font-bold text-primary transition hover:bg-primary hover:text-terminal-bg"
        >
          +
        </button>
      </form>
    </Panel>
  );
}
