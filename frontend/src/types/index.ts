// --- Enums ---
export type SignalAction = "buy" | "sell" | "close";
export type SignalStatus =
  | "active"
  | "closed_tp"
  | "closed_sl"
  | "closed_manual"
  | "expired";
export type ProviderSource = "tradingview" | "telegram" | "manual";
export type UserRole = "user" | "premium" | "admin";

// --- User ---
export interface User {
  id: string;
  email: string;
  username: string;
  role: UserRole;
  is_active: boolean;
  referral_code: string | null;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

// --- Signal ---
export interface Signal {
  id: string;
  provider_id: string;
  ticker: string;
  action: SignalAction;
  entry_price: number;
  take_profit: number | null;
  stop_loss: number | null;
  timeframe: string | null;
  status: SignalStatus;
  close_price: number | null;
  profit_pct: number | null;
  ai_confidence: number | null;
  ai_reasoning: string | null;
  created_at: string;
}

export interface SignalList {
  items: Signal[];
  total: number;
}

// --- Rating ---
export interface RatingFactor {
  score: number;
  weight: number;
  reason: string;
}

export interface RatingDetail {
  final_confidence: number;
  reasoning: string;
  factors: Record<string, RatingFactor>;
}

// --- Provider ---
export interface Provider {
  id: string;
  name: string;
  source: ProviderSource;
  description: string | null;
  is_active: boolean;
  total_signals: number;
  win_rate: number | null;
  avg_profit: number | null;
  ai_score: number | null;
  created_at: string;
}

export interface ProviderList {
  items: Provider[];
  total: number;
}

// --- WebSocket ---
export interface WSNewSignal {
  type: "new_signal";
  signal: {
    id: string;
    ticker: string;
    action: SignalAction;
    entry_price: number;
    take_profit: number | null;
    stop_loss: number | null;
    timeframe: string | null;
    ai_confidence: number | null;
    created_at: string | null;
  };
}

export interface WSConnected {
  type: "connected";
  message: string;
}

export type WSMessage = WSNewSignal | WSConnected | { type: "pong" };
