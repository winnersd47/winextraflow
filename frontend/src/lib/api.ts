import type {
  Token,
  User,
  SignalList,
  Signal,
  RatingDetail,
  ProviderList,
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
  async getLeaderboard(limit = 20): Promise<ProviderList> {
    return this.request<ProviderList>(
      `/providers/leaderboard?limit=${limit}`
    );
  }

  async getProviders(): Promise<ProviderList> {
    return this.request<ProviderList>("/providers");
  }
}

export const api = new ApiClient();
