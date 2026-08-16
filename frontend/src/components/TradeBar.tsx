"use client";

import { useEffect, useState } from "react";
import { money } from "@/lib/format";
import type { Side } from "@/lib/types";

interface TradeBarProps {
  ticker: string | null;
  lastPrice: number | null;
  cash: number;
  onTrade: (ticker: string, quantity: number, side: Side) => void | Promise<unknown>;
  error: string | null;
  onDismissError: () => void;
}

export function TradeBar({
  ticker,
  lastPrice,
  cash,
  onTrade,
  error,
  onDismissError,
}: TradeBarProps) {
  const [symbol, setSymbol] = useState(ticker ?? "");
  const [qty, setQty] = useState("1");
  const [pending, setPending] = useState(false);

  // Selecting a ticker anywhere in the terminal loads it into the order entry.
  useEffect(() => {
    if (ticker) setSymbol(ticker);
  }, [ticker]);

  const quantity = Number(qty);
  const valid = symbol.trim().length > 0 && Number.isFinite(quantity) && quantity > 0;
  const notional = valid && lastPrice ? quantity * lastPrice : null;

  async function submit(side: Side) {
    if (!valid || pending) return;
    setPending(true);
    await onTrade(symbol.trim().toUpperCase(), quantity, side);
    setPending(false);
  }

  return (
    <div className="flex shrink-0 flex-col border border-terminal-line bg-terminal-panel">
      <div className="flex items-stretch">
        <div className="flex items-center gap-1.5 border-r border-terminal-line px-3">
          <span className="eyebrow">Order</span>
        </div>

        <input
          value={symbol}
          onChange={(event) => setSymbol(event.target.value)}
          aria-label="Ticker"
          placeholder="SYMBOL"
          maxLength={12}
          className="w-28 border-r border-terminal-line bg-transparent px-3 py-2 font-mono text-[12px] uppercase tracking-wider text-terminal-text placeholder:text-terminal-faint focus:outline-none"
        />

        <input
          value={qty}
          onChange={(event) => setQty(event.target.value)}
          aria-label="Quantity"
          placeholder="QTY"
          inputMode="decimal"
          className="tnum w-24 border-r border-terminal-line bg-transparent px-3 py-2 text-[12px] text-terminal-text placeholder:text-terminal-faint focus:outline-none"
        />

        <div className="flex flex-1 items-center gap-4 px-3 text-[10px] text-terminal-dim">
          <span>
            Est. cost{" "}
            <span className="tnum text-terminal-text">{notional ? money(notional) : "—"}</span>
          </span>
          <span className="hidden lg:inline">
            Buying power <span className="tnum text-terminal-text">{money(cash)}</span>
          </span>
          <span className="ml-auto hidden text-terminal-faint xl:inline">
            Market order · instant fill · no fees
          </span>
        </div>

        <button
          type="button"
          disabled={!valid || pending}
          onClick={() => void submit("buy")}
          className="w-24 border-l border-terminal-line bg-secondary/85 text-[11px] font-bold uppercase tracking-[0.12em] text-white transition hover:bg-secondary disabled:opacity-40"
        >
          Buy
        </button>
        <button
          type="button"
          disabled={!valid || pending}
          onClick={() => void submit("sell")}
          className="w-24 border-l border-terminal-line bg-terminal-raised text-[11px] font-bold uppercase tracking-[0.12em] text-down transition hover:bg-down hover:text-terminal-bg disabled:opacity-40"
        >
          Sell
        </button>
      </div>

      {error && (
        <div
          role="alert"
          className="flex items-center gap-2 border-t border-down/40 bg-down/10 px-3 py-1.5 text-[11px] text-down"
        >
          <span className="flex-1">{error}</span>
          <button
            type="button"
            onClick={onDismissError}
            aria-label="Dismiss error"
            className="px-1 text-terminal-dim hover:text-terminal-text"
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
}
