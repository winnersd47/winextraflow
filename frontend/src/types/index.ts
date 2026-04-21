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
  sharpe_ratio: number | null;
  profit_factor: number | null;
  max_drawdown: number | null;
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

// --- Backtesting ---
export interface TradeResult {
  signal_id: string;
  ticker: string;
  action: string;
  entry_price: number;
  close_price: number;
  profit_pct: number;
  status: string;
  created_at: string;
}

export interface BacktestResult {
  provider_id: string | null;
  ticker: string | null;
  date_from: string | null;
  date_to: string | null;
  total_signals: number;
  closed_signals: number;
  active_signals: number;
  expired_signals: number;
  total_return_pct: number;
  win_rate: number;
  avg_profit_pct: number;
  avg_loss_pct: number;
  best_trade_pct: number;
  worst_trade_pct: number;
  sharpe_ratio: number | null;
  profit_factor: number | null;
  max_drawdown_pct: number;
  max_consecutive_wins: number;
  max_consecutive_losses: number;
  trades: TradeResult[];
  equity_curve: number[];
}

// --- Referral ---
export interface ReferralStats {
  referral_code: string;
  share_link: string;
  total_referrals: number;
  level1_count: number;
  level2_count: number;
  total_rewards: number;
  reward_type: string;
}

export interface ReferralUserInfo {
  id: string;
  username: string;
  email: string;
  created_at: string;
}

export interface ReferralTreeItem {
  user: ReferralUserInfo;
  level: number;
  status: string;
  reward_type: string | null;
  reward_amount: number | null;
  created_at: string;
}

export interface ReferralTree {
  referrals: ReferralTreeItem[];
  total: number;
}

// --- Execution ---
export type ExchangeName = "binance" | "bybit" | "demo";
export type OrderSide = "buy" | "sell";
export type OrderStatusType = "pending" | "filled" | "partial" | "failed" | "cancelled";

export interface ExchangeAccountResponse {
  id: string;
  exchange: ExchangeName;
  label: string;
  is_active: boolean;
  auto_execute: boolean;
  min_confidence: number;
  max_position_pct: number;
  created_at: string;
}

export interface OrderResponse {
  id: string;
  signal_id: string;
  exchange_account_id: string;
  exchange_order_id: string | null;
  exchange: string;
  symbol: string;
  side: OrderSide;
  order_type: string;
  quantity: number;
  price: number | null;
  filled_price: number | null;
  filled_quantity: number | null;
  status: OrderStatusType;
  error_message: string | null;
  created_at: string;
}

export interface OrderList {
  items: OrderResponse[];
  total: number;
}

// --- Marketplace ---
export type PriceType = "free" | "premium" | "paid";

export interface StrategyResponse {
  id: string;
  author_id: string;
  provider_id: string;
  name: string;
  description: string | null;
  tags: string | null;
  is_published: boolean;
  price_type: PriceType;
  price_monthly: number;
  subscriber_count: number;
  created_at: string;
  win_rate: number | null;
  avg_profit: number | null;
  ai_score: number | null;
  sharpe_ratio: number | null;
  total_signals: number;
}

export interface StrategyList {
  items: StrategyResponse[];
  total: number;
}

export interface SubscriptionResponse {
  id: string;
  user_id: string;
  strategy_id: string;
  status: string;
  auto_execute: boolean;
  expires_at: string | null;
  created_at: string;
}

// --- Copy Trading ---
export interface CopyTradeResponse {
  id: string;
  subscriber_id: string;
  strategy_id: string;
  signal_id: string;
  order_id: string | null;
  status: string;
  error_message: string | null;
  created_at: string;
}

export interface CopyTradingStatus {
  enabled: boolean;
  active_subscriptions: number;
  auto_execute_accounts: number;
  total_copied_trades: number;
  successful_trades: number;
  failed_trades: number;
}

export interface CopyTradeList {
  items: CopyTradeResponse[];
  total: number;
}

// --- Gamification ---
export interface AchievementResponse {
  id: string;
  code: string;
  name: string;
  description: string;
  icon: string;
  category: string;
  xp_reward: number;
  requirement_value: number;
  is_hidden: boolean;
  progress: number;
  is_unlocked: boolean;
}

export interface UserXP {
  total_xp: number;
  level: number;
  current_level_xp: number;
  next_level_xp: number;
  progress_pct: number;
}

export interface ProfileResponse {
  xp: UserXP;
  achievements: AchievementResponse[];
  unlocked_count: number;
  total_count: number;
}

// --- Premium ---
export interface PremiumStatus {
  is_premium: boolean;
  days_left: number;
  role: string;
  expires_at: string | null;
}

// --- Notifications ---
export interface NotificationResponse {
  id: string;
  type: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

export interface NotificationList {
  items: NotificationResponse[];
  total: number;
}
