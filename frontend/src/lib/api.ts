import type {
  ChatResponse,
  Portfolio,
  Position,
  Side,
  Snapshot,
  WatchlistItem,
} from "./types";

// Matches backend/app/api/portfolio.py's DEFAULT_HISTORY_LIMIT — a long-running
// session accumulates snapshots every 30s indefinitely, so the default request must
// stay bounded instead of pulling the full unbounded history on every poll.
const DEFAULT_HISTORY_LIMIT = 500;

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: init?.body ? { "Content-Type": "application/json", ...init?.headers } : init?.headers,
  });

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // Non-JSON error body; keep the generic message.
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const num = (v: unknown): number => (typeof v === "number" && Number.isFinite(v) ? v : 0);

function normalizePosition(raw: Record<string, unknown>): Position {
  const quantity = num(raw.quantity);
  const avgCost = num(raw.avg_cost);
  const currentPrice = num(raw.current_price);
  const costBasis = quantity * avgCost;
  const pnl =
    typeof raw.unrealized_pnl === "number"
      ? raw.unrealized_pnl
      : quantity * currentPrice - costBasis;

  return {
    ticker: String(raw.ticker ?? ""),
    quantity,
    avg_cost: avgCost,
    current_price: currentPrice,
    unrealized_pnl: pnl,
    unrealized_pnl_percent:
      typeof raw.unrealized_pnl_percent === "number"
        ? raw.unrealized_pnl_percent
        : costBasis > 0
          ? (pnl / costBasis) * 100
          : 0,
    stale: raw.stale === true,
  };
}

export async function fetchPortfolio(): Promise<Portfolio> {
  const raw = await request<Record<string, unknown>>("/api/portfolio");
  const positions = Array.isArray(raw.positions)
    ? (raw.positions as Record<string, unknown>[]).map(normalizePosition)
    : [];
  return {
    cash_balance: num(raw.cash_balance),
    positions,
    total_value: num(raw.total_value),
  };
}

export async function fetchHistory(limit: number = DEFAULT_HISTORY_LIMIT): Promise<Snapshot[]> {
  const raw = await request<unknown>(`/api/portfolio/history?limit=${limit}`);
  const rows = Array.isArray(raw)
    ? raw
    : Array.isArray((raw as Record<string, unknown>)?.snapshots)
      ? ((raw as Record<string, unknown>).snapshots as unknown[])
      : [];
  return (rows as Record<string, unknown>[]).map((r) => ({
    total_value: num(r.total_value),
    recorded_at: String(r.recorded_at ?? ""),
  }));
}

/** The watchlist may come back as bare symbols or as objects with a price. */
export async function fetchWatchlist(): Promise<WatchlistItem[]> {
  const raw = await request<unknown>("/api/watchlist");
  const rows = Array.isArray(raw)
    ? raw
    : Array.isArray((raw as Record<string, unknown>)?.watchlist)
      ? ((raw as Record<string, unknown>).watchlist as unknown[])
      : [];

  return rows.map((row) => {
    if (typeof row === "string") return { ticker: row, price: null };
    const r = row as Record<string, unknown>;
    return {
      ticker: String(r.ticker ?? ""),
      price: typeof r.price === "number" ? r.price : null,
    };
  });
}

export function addTicker(ticker: string) {
  return request<unknown>("/api/watchlist", {
    method: "POST",
    body: JSON.stringify({ ticker: ticker.trim().toUpperCase() }),
  });
}

export function removeTicker(ticker: string) {
  return request<unknown>(`/api/watchlist/${encodeURIComponent(ticker)}`, { method: "DELETE" });
}

export function executeTrade(ticker: string, quantity: number, side: Side) {
  return request<unknown>("/api/portfolio/trade", {
    method: "POST",
    body: JSON.stringify({ ticker: ticker.trim().toUpperCase(), quantity, side }),
  });
}

export async function sendChat(message: string): Promise<ChatResponse> {
  const raw = await request<Record<string, unknown>>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
  return {
    message: String(raw.message ?? ""),
    trade_results: Array.isArray(raw.trade_results) ? (raw.trade_results as ChatResponse["trade_results"]) : [],
    watchlist_results: Array.isArray(raw.watchlist_results)
      ? (raw.watchlist_results as ChatResponse["watchlist_results"])
      : [],
  };
}
