import type {
  Token,
  User,
  SignalList,
  Signal,
  RatingDetail,
  ProviderList,
  BacktestResult,
  ReferralStats,
  ReferralTree,
  ExchangeAccountResponse,
  OrderList,
  OrderResponse,
  StrategyList,
  StrategyResponse,
  SubscriptionResponse,
  CopyTradingStatus,
  CopyTradeList,
  ProfileResponse,
  PremiumStatus,
  NotificationList,
} from "@/types";

const API_BASE = "/api/v1";

class ApiClient {
  private getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("token");
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...((options.headers as Record<string, string>) || {}),
    };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });

    if (res.status === 401) {
      localStorage.removeItem("token");
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      throw new Error("Unauthorized");
    }

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(error.detail || `HTTP ${res.status}`);
    }

    return res.json();
  }

  // --- Auth ---
  async login(email: string, password: string): Promise<Token> {
    const data = await this.request<Token>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    localStorage.setItem("token", data.access_token);
    return data;
  }

  async register(
    email: string,
    username: string,
    password: string,
    referralCode?: string
  ): Promise<User> {
    return this.request<User>("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        email,
        username,
        password,
        referral_code: referralCode || null,
      }),
    });
  }

  async getMe(): Promise<User> {
    return this.request<User>("/auth/me");
  }

  async getTelegramLink(): Promise<{ enabled: boolean; link: string | null; linked: boolean; notifications: boolean }> {
    return this.request("/auth/telegram-link");
  }

  async toggleTelegramNotifications(enabled: boolean): Promise<void> {
    await this.request(`/auth/telegram-notifications?enabled=${enabled}`, { method: "PATCH" });
  }

  logout() {
    localStorage.removeItem("token");
    window.location.href = "/login";
  }

  // --- Signals ---
  async getSignals(params?: {
    ticker?: string;
    status?: string;
    provider_id?: string;
    skip?: number;
    limit?: number;
  }): Promise<SignalList> {
    const query = new URLSearchParams();
    if (params?.ticker) query.set("ticker", params.ticker);
    if (params?.status) query.set("status", params.status);
    if (params?.provider_id) query.set("provider_id", params.provider_id);
    if (params?.skip) query.set("skip", String(params.skip));
    if (params?.limit) query.set("limit", String(params.limit));
    const qs = query.toString();
    return this.request<SignalList>(`/signals${qs ? `?${qs}` : ""}`);
  }

  async getSignal(id: string): Promise<Signal> {
    return this.request<Signal>(`/signals/${id}`);
  }

  async getSignalRating(id: string): Promise<RatingDetail> {
    return this.request<RatingDetail>(`/signals/${id}/rating`);
  }

  // --- Providers ---
  async createProvider(data: { name: string; source: string; description?: string }): Promise<any> {
    return this.request("/providers", { method: "POST", body: JSON.stringify(data) });
  }

  // --- Admin ---
  async getCapacityReport(): Promise<any> {
    return this.request("/admin/capacity");
  }

  async getCapacityAlert(): Promise<any> {
    return this.request("/admin/capacity/alert");
  }

  async getLeaderboard(limit = 20): Promise<ProviderList> {
    return this.request<ProviderList>(
      `/providers/leaderboard?limit=${limit}`
    );
  }

  async getProviders(): Promise<ProviderList> {
    return this.request<ProviderList>("/providers");
  }

  // --- Backtesting ---
  async runBacktest(params: {
    provider_id?: string;
    ticker?: string;
    date_from?: string;
    date_to?: string;
    initial_capital?: number;
  }): Promise<BacktestResult> {
    return this.request<BacktestResult>("/backtest", {
      method: "POST",
      body: JSON.stringify(params),
    });
  }

  // --- Referrals ---
  async getReferralStats(): Promise<ReferralStats> {
    return this.request<ReferralStats>("/referrals/stats");
  }

  async getReferralTree(): Promise<ReferralTree> {
    return this.request<ReferralTree>("/referrals/tree");
  }

  // --- Execution ---
  async getExchangeAccounts(): Promise<ExchangeAccountResponse[]> {
    return this.request<ExchangeAccountResponse[]>("/execution/accounts");
  }

  async createExchangeAccount(data: {
    exchange: string;
    label: string;
    api_key: string;
    api_secret: string;
    auto_execute?: boolean;
  }): Promise<ExchangeAccountResponse> {
    return this.request<ExchangeAccountResponse>("/execution/accounts", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async executeSignal(
    signalId: string,
    accountId: string,
    quantity?: number
  ): Promise<OrderResponse> {
    return this.request<OrderResponse>(`/execution/execute/${signalId}`, {
      method: "POST",
      body: JSON.stringify({
        exchange_account_id: accountId,
        order_type: "market",
        quantity: quantity || null,
      }),
    });
  }

  async getOrders(skip = 0, limit = 50): Promise<OrderList> {
    return this.request<OrderList>(`/execution/orders?skip=${skip}&limit=${limit}`);
  }

  // --- Marketplace ---
  async browseStrategies(params?: {
    price_type?: string;
    tags?: string;
    sort_by?: string;
  }): Promise<StrategyList> {
    const query = new URLSearchParams();
    if (params?.price_type) query.set("price_type", params.price_type);
    if (params?.tags) query.set("tags", params.tags);
    if (params?.sort_by) query.set("sort_by", params.sort_by);
    const qs = query.toString();
    return this.request<StrategyList>(`/strategies${qs ? `?${qs}` : ""}`);
  }

  async getStrategy(id: string): Promise<StrategyResponse> {
    return this.request<StrategyResponse>(`/strategies/${id}`);
  }

  async subscribeStrategy(id: string): Promise<SubscriptionResponse> {
    return this.request<SubscriptionResponse>(`/strategies/${id}/subscribe`, {
      method: "POST",
    });
  }

  async unsubscribeStrategy(id: string): Promise<void> {
    await this.request(`/strategies/${id}/subscribe`, { method: "DELETE" });
  }

  async getMySubscriptions(): Promise<SubscriptionResponse[]> {
    return this.request<SubscriptionResponse[]>("/strategies/subscriptions");
  }

  // --- Copy Trading ---
  async getCopyTradingStatus(): Promise<CopyTradingStatus> {
    return this.request<CopyTradingStatus>("/copy-trading/status");
  }

  async getCopyTradeHistory(skip = 0, limit = 50): Promise<CopyTradeList> {
    return this.request<CopyTradeList>(`/copy-trading/history?skip=${skip}&limit=${limit}`);
  }

  async toggleAutoExecute(subscriptionId: string, enable: boolean): Promise<void> {
    await this.request(`/copy-trading/subscriptions/${subscriptionId}/auto-execute?enable=${enable}`, {
      method: "PATCH",
    });
  }

  // --- Gamification ---
  async getProfile(): Promise<ProfileResponse> {
    return this.request<ProfileResponse>("/achievements/profile");
  }

  // --- Premium ---
  async getPremiumStatus(): Promise<PremiumStatus> {
    return this.request<PremiumStatus>("/premium/status");
  }

  async activatePremium(promoCode: string): Promise<PremiumStatus> {
    return this.request<PremiumStatus>("/premium/activate", {
      method: "POST",
      body: JSON.stringify({ promo_code: promoCode }),
    });
  }

  // --- Notifications ---
  async getNotifications(skip = 0, limit = 20): Promise<NotificationList> {
    return this.request<NotificationList>(`/notifications?skip=${skip}&limit=${limit}`);
  }

  async getUnreadCount(): Promise<{ count: number }> {
    return this.request<{ count: number }>("/notifications/unread-count");
  }

  async markNotificationRead(id: string): Promise<void> {
    await this.request(`/notifications/${id}/read`, { method: "PATCH" });
  }

  async markAllRead(): Promise<void> {
    await this.request("/notifications/read-all", { method: "PATCH" });
  }

  // --- Telegram ---
  async resolveTelegramChannel(username: string): Promise<{ id: string; title: string; username: string }> {
    return this.request<any>(`/providers/telegram/resolve?username=${encodeURIComponent(username)}`);
  }

  async subscribeTelegram(providerId: string, data: { channel_id?: string; channel_username?: string; channel_name?: string }): Promise<any> {
    return this.request(`/providers/${providerId}/subscribe`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async unsubscribeTelegram(providerId: string): Promise<any> {
    return this.request(`/providers/${providerId}/subscribe`, { method: "DELETE" });
  }

  async getProviderStatus(providerId: string): Promise<any> {
    return this.request(`/providers/${providerId}/status`);
  }

  // --- Payments (YooKassa / CryptoCloud / Prodamus) ---
  async createCheckout(plan: string): Promise<{ payment_url: string; payment_id: string; demo: boolean }> {
    return this.request("/payments/checkout", {
      method: "POST",
      body: JSON.stringify({
        plan,
        return_url: `${window.location.origin}/dashboard/store`,
      }),
    });
  }

  async completeDemoPayment(paymentId: string): Promise<{ status: string; plan: string; days: number }> {
    return this.request(`/payments/complete-demo?payment_id=${paymentId}`, { method: "POST" });
  }

  async getPaymentHistory(): Promise<{ total: number; items: any[] }> {
    return this.request("/payments/history");
  }
}

export const api = new ApiClient();
