export type Direction = "up" | "down" | "flat";
export type Side = "buy" | "sell";
export type ActionStatus = "executed" | "failed";

export interface PriceUpdate {
  ticker: string;
  price: number;
  previous_price: number;
  timestamp: number;
  change: number;
  change_percent: number;
  direction: Direction;
}

export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  unrealized_pnl: number;
  unrealized_pnl_percent: number;
  /** True when the backend priced this position at avg_cost because it has no market data for the ticker. */
  stale: boolean;
}

export interface Portfolio {
  cash_balance: number;
  positions: Position[];
  total_value: number;
}

export interface Snapshot {
  total_value: number;
  recorded_at: string;
}

export interface WatchlistItem {
  ticker: string;
  price: number | null;
}

export interface TradeResult {
  ticker: string;
  side: Side;
  quantity: number;
  status: ActionStatus;
  /** Executed trade row from the backend; carries the fill price. */
  trade?: { price?: number } | null;
  error?: string | null;
}

export interface WatchlistResult {
  ticker: string;
  action: "add" | "remove";
  status: ActionStatus;
  error?: string | null;
}

export interface ChatResponse {
  message: string;
  trade_results: TradeResult[];
  watchlist_results: WatchlistResult[];
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  trade_results?: TradeResult[];
  watchlist_results?: WatchlistResult[];
  failed?: boolean;
}

export type ConnectionStatus = "connecting" | "connected" | "reconnecting" | "disconnected";
