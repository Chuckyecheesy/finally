"use client";

import { useMemo } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";
import { Panel } from "./Panel";
import { money } from "@/lib/format";
import type { Snapshot } from "@/lib/types";

interface PnlChartProps {
  snapshots: Snapshot[];
}

export function PnlChart({ snapshots }: PnlChartProps) {
  const data = useMemo(
    () =>
      snapshots.map((snapshot) => ({
        value: snapshot.total_value,
        label: new Date(snapshot.recorded_at).toLocaleTimeString("en-US", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
      })),
    [snapshots],
  );

  const first = data[0]?.value;
  const last = data[data.length - 1]?.value;
  const rising = first !== undefined && last !== undefined ? last >= first : true;

  return (
    <Panel title="Portfolio Value" bodyClassName="p-1">
      {data.length < 2 ? (
        <div className="flex h-full items-center justify-center px-3 text-center text-[11px] text-terminal-dim">
          Snapshots are recorded every 30 seconds and after each trade.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 6, right: 6, bottom: 2, left: 0 }}>
            <CartesianGrid stroke="var(--color-terminal-line)" strokeDasharray="1 4" vertical={false} />
            <YAxis
              domain={["dataMin", "dataMax"]}
              width={58}
              orientation="right"
              tick={{ fill: "var(--color-terminal-faint)", fontSize: 10, fontFamily: "var(--font-mono)" }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value: number) => value.toFixed(0)}
            />
            <Tooltip
              contentStyle={{
                background: "var(--color-terminal-raised)",
                border: "1px solid var(--color-terminal-line-bright)",
                borderRadius: 0,
                fontSize: 11,
                fontFamily: "var(--font-mono)",
              }}
              labelStyle={{ color: "var(--color-terminal-dim)" }}
              formatter={(value) => [money(Number(value ?? 0)), "Value"]}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke={rising ? "var(--color-primary)" : "var(--color-down)"}
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}
