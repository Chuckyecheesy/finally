"use client";

import { useMemo } from "react";
import { ResponsiveContainer, Treemap } from "recharts";
import { Panel } from "./Panel";
import { percent } from "@/lib/format";
import type { Position } from "@/lib/types";

interface HeatmapProps {
  positions: Position[];
  onSelect: (ticker: string) => void;
}

interface Cell {
  name: string;
  size: number;
  pnlPercent: number;
  [key: string]: string | number;
}

/** Maps P&L% to a tinted fill; ±5% saturates so small moves stay readable. */
function fillFor(pnlPercent: number): string {
  const intensity = Math.min(Math.abs(pnlPercent) / 5, 1);
  const alpha = 12 + intensity * 58;
  const hue = pnlPercent >= 0 ? "var(--color-up)" : "var(--color-down)";
  return `color-mix(in srgb, ${hue} ${alpha.toFixed(0)}%, var(--color-terminal-panel))`;
}

interface CellProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  pnlPercent?: number;
  onSelect?: (ticker: string) => void;
}

function HeatmapCell({ x = 0, y = 0, width = 0, height = 0, name, pnlPercent = 0, onSelect }: CellProps) {
  if (!name || width <= 0 || height <= 0) return null;
  const showLabel = width > 44 && height > 26;

  return (
    <g
      onClick={() => onSelect?.(name)}
      className="cursor-pointer"
      role="listitem"
      aria-label={`${name} ${percent(pnlPercent)}`}
    >
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={fillFor(pnlPercent)}
        stroke="var(--color-terminal-bg)"
        strokeWidth={1}
      />
      {showLabel && (
        <>
          <text
            x={x + 6}
            y={y + 15}
            fill="var(--color-terminal-text)"
            fontSize={11}
            fontWeight={700}
            fontFamily="var(--font-mono)"
          >
            {name}
          </text>
          <text
            x={x + 6}
            y={y + 27}
            fill={pnlPercent >= 0 ? "var(--color-up)" : "var(--color-down)"}
            fontSize={10}
            fontFamily="var(--font-mono)"
          >
            {percent(pnlPercent)}
          </text>
        </>
      )}
    </g>
  );
}

export function Heatmap({ positions, onSelect }: HeatmapProps) {
  const data = useMemo<Cell[]>(
    () =>
      positions
        .filter((position) => position.quantity > 0 && position.current_price > 0)
        .map((position) => ({
          name: position.ticker,
          size: position.quantity * position.current_price,
          pnlPercent: position.unrealized_pnl_percent,
        })),
    [positions],
  );

  return (
    <Panel title="Allocation" bodyClassName="p-1">
      {data.length === 0 ? (
        <div className="flex h-full items-center justify-center px-3 text-center text-[11px] text-terminal-dim">
          Buy a position and it appears here, sized by weight.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <Treemap
            data={data}
            dataKey="size"
            isAnimationActive={false}
            content={<HeatmapCell onSelect={onSelect} />}
          />
        </ResponsiveContainer>
      )}
    </Panel>
  );
}
