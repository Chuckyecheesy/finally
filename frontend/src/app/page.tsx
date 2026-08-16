"use client";

import { useEffect, useState } from "react";
import { ChatPanel } from "@/components/ChatPanel";
import { Header } from "@/components/Header";
import { Heatmap } from "@/components/Heatmap";
import { PnlChart } from "@/components/PnlChart";
import { PositionsTable } from "@/components/PositionsTable";
import { PriceChart } from "@/components/PriceChart";
import { TradeBar } from "@/components/TradeBar";
import { Watchlist } from "@/components/Watchlist";
import { usePriceStream } from "@/hooks/usePriceStream";
import { useTerminal } from "@/hooks/useTerminal";

export default function Terminal() {
  const { prices, history: tickHistory, status } = usePriceStream();
  const terminal = useTerminal(prices);
  const [selected, setSelected] = useState<string | null>(null);
  const [chatCollapsed, setChatCollapsed] = useState(false);

  // Land on the first watched ticker so the chart is never empty on arrival.
  useEffect(() => {
    if (!selected && terminal.watchlist.length > 0) {
      setSelected(terminal.watchlist[0].ticker);
    }
  }, [selected, terminal.watchlist]);

  const costBasis = terminal.positions.reduce((sum, p) => sum + p.quantity * p.avg_cost, 0);
  const selectedPrice = selected ? (prices[selected]?.price ?? null) : null;

  return (
    <div className="flex h-screen flex-col">
      <Header
        totalValue={terminal.totalValue}
        cash={terminal.cash}
        unrealizedPnl={terminal.unrealizedPnl}
        unrealizedPnlPercent={costBasis > 0 ? (terminal.unrealizedPnl / costBasis) * 100 : 0}
        status={status}
      />

      <main className="grid min-h-0 flex-1 grid-cols-[248px_minmax(0,1fr)_auto] gap-px bg-terminal-bg p-px">
        <Watchlist
          items={terminal.watchlist}
          prices={prices}
          history={tickHistory}
          selected={selected}
          onSelect={setSelected}
          onAdd={terminal.addTicker}
          onRemove={terminal.removeTicker}
        />

        <div className="grid min-h-0 min-w-0 grid-rows-[minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,0.8fr)_auto] gap-px">
          <PriceChart
            ticker={selected}
            points={selected ? (tickHistory[selected] ?? []) : []}
            update={selected ? prices[selected] : undefined}
          />

          <div className="grid min-h-0 grid-cols-2 gap-px">
            <Heatmap positions={terminal.positions} onSelect={setSelected} />
            <PnlChart snapshots={terminal.history} />
          </div>

          <PositionsTable
            positions={terminal.positions}
            selected={selected}
            onSelect={setSelected}
          />

          <TradeBar
            ticker={selected}
            lastPrice={selectedPrice}
            cash={terminal.cash}
            onTrade={terminal.trade}
            error={terminal.error}
            onDismissError={terminal.dismissError}
          />
        </div>

        <ChatPanel
          onActions={terminal.refresh}
          collapsed={chatCollapsed}
          onToggle={() => setChatCollapsed((value) => !value)}
        />
      </main>
    </div>
  );
}
