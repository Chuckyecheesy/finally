"use client";

import { useMemo } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, YAxis } from "recharts";
import { Panel } from "./Panel";
import { percent, price as formatPrice } from "@/lib/format";
import type { PriceUpdate } from "@/lib/types";

interface PriceChartProps {
  ticker: string | null;
  points: number[];
  update?: PriceUpdate;
}

export function PriceChart({ ticker, points, update }: PriceChartProps) {
  const data = useMemo(() => points.map((value, index) => ({ index, value })), [points]);

  const first = points[0];
  const last = points[points.length - 1];
  const sessionChange = first && last ? ((last - first) / first) * 100 : 0;
  const rising = sessionChange >= 0;
  const stroke = rising ? "var(--color-up)" : "var(--color-down)";

  return (
    <Panel
      title={ticker ? `${ticker} · Session` : "Session"}
      aside={
        update ? (
          <span className="flex items-baseline gap-2">
            <span className="tnum text-[13px] text-terminal-text">{formatPrice(update.price)}</span>
            <span className={`tnum text-[10px] ${rising ? "text-up" : "text-down"}`}>
              {percent(sessionChange)}
            </span>
          </span>
        ) : null
      }
      bodyClassName="p-1"
    >
      {data.length < 2 ? (
        <div className="flex h-full items-center justify-center text-[11px] text-terminal-dim">
          {ticker
            ? "Collecting ticks — the chart draws as prices stream in."
            : "Select a ticker from the watchlist."}
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 6, right: 6, bottom: 2, left: 0 }}>
            <defs>
              <linearGradient id="price-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={stroke} stopOpacity={0.28} />
                <stop offset="100%" stopColor={stroke} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="var(--color-terminal-line)" strokeDasharray="1 4" vertical={false} />
            <YAxis
              domain={["dataMin", "dataMax"]}
              width={54}
              orientation="right"
              tick={{ fill: "var(--color-terminal-faint)", fontSize: 10, fontFamily: "var(--font-mono)" }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value: number) => value.toFixed(2)}
            />
            <Area
              type="linear"
              dataKey="value"
              stroke={stroke}
              strokeWidth={1.25}
              fill="url(#price-fill)"
              isAnimationActive={false}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}
