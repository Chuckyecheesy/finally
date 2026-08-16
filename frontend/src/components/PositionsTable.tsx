"use client";

import { Panel } from "./Panel";
import { PriceCell } from "./PriceCell";
import { money, percent, pnlColor, quantity as formatQuantity, signedMoney } from "@/lib/format";
import type { Position } from "@/lib/types";

interface PositionsTableProps {
  positions: Position[];
  selected: string | null;
  onSelect: (ticker: string) => void;
}

const HEADERS = ["Symbol", "Qty", "Avg Cost", "Last", "Market Value", "Unrealized", "%"];

export function PositionsTable({ positions, selected, onSelect }: PositionsTableProps) {
  return (
    <Panel
      title="Positions"
      aside={<span className="tnum text-[10px] text-terminal-faint">{positions.length}</span>}
      bodyClassName="overflow-auto"
    >
      {positions.length === 0 ? (
        <div className="flex h-full items-center justify-center text-[11px] text-terminal-dim">
          No open positions.
        </div>
      ) : (
        <table className="w-full border-collapse text-[11px]">
          <thead className="sticky top-0 bg-terminal-panel">
            <tr className="border-b border-terminal-line">
              {HEADERS.map((header, index) => (
                <th
                  key={header}
                  scope="col"
                  className={`eyebrow px-2 py-1.5 font-bold ${index === 0 ? "text-left" : "text-right"}`}
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {positions.map((position) => (
              <tr
                key={position.ticker}
                onClick={() => onSelect(position.ticker)}
                className={`cursor-pointer border-b border-terminal-line/50 transition-colors hover:bg-terminal-raised ${
                  selected === position.ticker ? "bg-terminal-raised" : ""
                }`}
              >
                <td className="px-2 py-1 font-mono text-[11px] font-bold text-terminal-text">
                  {position.ticker}
                </td>
                <td className="tnum px-2 py-1 text-right text-terminal-dim">
                  {formatQuantity(position.quantity)}
                </td>
                <td className="tnum px-2 py-1 text-right text-terminal-dim">
                  {position.avg_cost.toFixed(2)}
                </td>
                <td className="px-1 py-1 text-right">
                  <PriceCell value={position.current_price} />
                </td>
                <td className="tnum px-2 py-1 text-right">
                  {money(position.quantity * position.current_price)}
                </td>
                <td className={`tnum px-2 py-1 text-right ${pnlColor(position.unrealized_pnl)}`}>
                  {signedMoney(position.unrealized_pnl)}
                </td>
                <td className={`tnum px-2 py-1 text-right ${pnlColor(position.unrealized_pnl)}`}>
                  {percent(position.unrealized_pnl_percent)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  );
}
