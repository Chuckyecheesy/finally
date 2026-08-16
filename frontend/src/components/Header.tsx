import { money, percent, pnlColor, signedMoney } from "@/lib/format";
import type { ConnectionStatus } from "@/lib/types";

const STATUS_STYLE: Record<ConnectionStatus, { dot: string; label: string }> = {
  connecting: { dot: "bg-accent", label: "Connecting" },
  connected: { dot: "bg-up", label: "Live" },
  reconnecting: { dot: "bg-accent", label: "Reconnecting" },
  disconnected: { dot: "bg-down", label: "Offline" },
};

interface HeaderProps {
  totalValue: number;
  cash: number;
  unrealizedPnl: number;
  unrealizedPnlPercent: number;
  status: ConnectionStatus;
}

function Stat({ label, value, className = "" }: { label: string; value: string; className?: string }) {
  return (
    <div className="flex flex-col justify-center border-l border-terminal-line px-4">
      <span className="eyebrow leading-none">{label}</span>
      <span className={`tnum mt-1 text-[15px] leading-none ${className}`}>{value}</span>
    </div>
  );
}

export function Header({
  totalValue,
  cash,
  unrealizedPnl,
  unrealizedPnlPercent,
  status,
}: HeaderProps) {
  const indicator = STATUS_STYLE[status];
  const live = status === "connected";

  return (
    <header className="flex h-14 shrink-0 items-stretch border-b border-terminal-line bg-terminal-panel">
      <div className="flex items-center gap-2 px-4">
        <span className="font-mono text-[17px] font-extrabold tracking-[-0.04em] text-terminal-text">
          FINALLY
        </span>
        <span
          aria-hidden
          className={`h-[15px] w-[7px] bg-accent ${live ? "animate-pulse" : "opacity-30"}`}
        />
      </div>

      <Stat label="Total Value" value={money(totalValue)} className="text-accent" />
      <Stat label="Cash" value={money(cash)} />
      <Stat
        label="Unrealized P&L"
        value={`${signedMoney(unrealizedPnl)}  ${percent(unrealizedPnlPercent)}`}
        className={pnlColor(unrealizedPnl)}
      />

      <div className="ml-auto flex items-center gap-2 border-l border-terminal-line px-4">
        <span
          data-testid="connection-dot"
          data-status={status}
          aria-hidden
          className={`h-2 w-2 rounded-full ${indicator.dot} ${live ? "" : "animate-pulse"}`}
        />
        <span className="eyebrow" role="status">
          {indicator.label}
        </span>
      </div>
    </header>
  );
}
