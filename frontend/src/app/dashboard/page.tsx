"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useWebSocket } from "@/lib/ws";
import { useI18n } from "@/lib/i18n";
import { useAuth } from "@/lib/auth";
import { SignalCard } from "@/components/signal-card";
import type { Signal, WSNewSignal } from "@/types";

const REGIME_RU: Record<string, string> = {
  trending_up: "Тренд вверх", trending_down: "Тренд вниз", ranging: "Боковик",
  high_volatility: "Высокая вол.", low_volatility: "Низкая вол.", breakout: "Пробой", unknown: "",
};

export default function DashboardPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const [tickerFilter, setTickerFilter] = useState("");
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [regime, setRegime] = useState<any>(null);
  const [evaluations, setEvaluations] = useState<Record<string, any>>({});
  const { t, locale } = useI18n();
  const { user } = useAuth();
  const isRu = locale === "ru";
  const isPremium = user?.role === "premium" || user?.role === "admin";

  const fetchSignals = useCallback(async (showSpinner = false) => {
    if (showSpinner) setRefreshing(true);
    try {
      const data = await api.getSignals({
        status: statusFilter || undefined,
        ticker: tickerFilter || undefined,
        limit: 50,
      });
      setSignals(data.items);
      setTotal(data.total);
      setLastUpdate(new Date());
    } catch (err) {
      console.error("Failed to fetch signals:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [statusFilter, tickerFilter]);

  // Fetch market regime (L1 — available to all)
  useEffect(() => {
    const loadRegime = async () => {
      try {
        const token = localStorage.getItem("token");
        const resp = await fetch("/api/v1/quant/regime", { headers: { Authorization: `Bearer ${token}` } });
        if (resp.ok) setRegime(await resp.json());
      } catch {}
    };
    loadRegime();
  }, []);

  // Fetch signal evaluations for Premium (L2)
  useEffect(() => {
    if (!isPremium || signals.length === 0) return;
    const loadEvals = async () => {
      try {
        const token = localStorage.getItem("token");
        const resp = await fetch("/api/v1/quant/dashboard", { headers: { Authorization: `Bearer ${token}` } });
        if (resp.ok) {
          const data = await resp.json();
          const map: Record<string, any> = {};
          for (const e of data.evaluations || []) {
            map[e.signal_id] = e;
          }
          setEvaluations(map);
        }
      } catch {}
    };
    loadEvals();
  }, [isPremium, signals.length]);

  useEffect(() => { fetchSignals(); }, [fetchSignals]);

  const handleNewSignal = useCallback((_msg: WSNewSignal) => { fetchSignals(); }, [fetchSignals]);
  const { connected } = useWebSocket(handleNewSignal);

  const handleManualRefresh = () => { fetchSignals(true); };

  const STATUS_FILTERS = [
    { value: "", label: t("signals.all") },
    { value: "active", label: t("signals.active") },
    { value: "closed_tp", label: t("signals.tpHit") },
    { value: "closed_sl", label: t("signals.slHit") },
    { value: "expired", label: t("signals.expired") },
  ];

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">{t("signals.title")}</h1>
          <p className="text-sm text-text-secondary">
            {total} {t("signals.total")}{" "}
            <span className={`ml-2 inline-block h-2 w-2 rounded-full ${connected ? "bg-green-500" : "bg-red-500"}`} />
            <span className="ml-1 text-xs">{connected ? t("signals.live") : t("signals.reconnecting")}</span>
            {lastUpdate && (
              <span className="ml-3 text-xs text-text-muted">
                {t("signals.lastUpdate")}: {lastUpdate.toLocaleTimeString()}
              </span>
            )}
          </p>
        </div>
        <button
          onClick={handleManualRefresh}
          disabled={refreshing}
          className="flex items-center gap-2 rounded-lg border border-border bg-surface-card px-4 py-2 text-sm font-medium text-text-primary transition hover:bg-surface-hover disabled:opacity-50"
        >
          <svg className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" /><path d="M3 3v5h5" />
            <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" /><path d="M16 16h5v5" />
          </svg>
          {refreshing ? t("signals.refreshing") : t("signals.refresh")}
        </button>
      </div>

      {/* L1: Market Regime Banner — available to ALL users */}
      {regime && regime.regime !== "unknown" && (
        <div className="mb-4 flex items-center gap-4 rounded-xl border border-border bg-surface-card px-4 py-3">
          <div>
            <span className="text-xs text-text-muted">{isRu ? "Режим рынка" : "Market Regime"}</span>
            <p className="text-sm font-bold text-brand-500">
              {isRu ? (REGIME_RU[regime.regime] || regime.regime) : regime.regime.replace("_", " ")}
            </p>
          </div>
          <div className="text-center">
            <span className="text-xs text-text-muted">{isRu ? "Уверенность" : "Confidence"}</span>
            <p className="text-sm font-bold text-text-primary">{(regime.confidence * 100).toFixed(0)}%</p>
          </div>
          <div className="text-center">
            <span className="text-xs text-text-muted">{isRu ? "Волатильность" : "Volatility"}</span>
            <p className="text-sm font-bold text-text-primary">{regime.volatility_proxy?.toFixed(1)}</p>
          </div>
          <div className="text-center">
            <span className="text-xs text-text-muted">Buy/Sell</span>
            <p className="text-sm font-bold text-text-primary">{(regime.buy_ratio * 100).toFixed(0)}% / {((1 - regime.buy_ratio) * 100).toFixed(0)}%</p>
          </div>
          {!isPremium && (
            <div className="ml-auto rounded bg-brand-500/10 px-3 py-1 text-xs text-brand-500">
              L1 {isRu ? "Базовая аналитика" : "Basic Analytics"}
            </div>
          )}
          {isPremium && (
            <div className="ml-auto rounded bg-green-500/10 px-3 py-1 text-xs text-green-400">
              L2 {isRu ? "Полная аналитика" : "Full Analytics"}
            </div>
          )}
        </div>
      )}

      <div className="mb-4 flex flex-wrap gap-3">
        <select value={tickerFilter} onChange={(e) => setTickerFilter(e.target.value)} className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary">
          <option value="">{isRu ? "Все тикеры" : "All tickers"}</option>
          <optgroup label={isRu ? "Крипто" : "Crypto"}>
            <option value="BTCUSDT">BTCUSDT — Bitcoin</option>
            <option value="ETHUSDT">ETHUSDT — Ethereum</option>
            <option value="SOLUSDT">SOLUSDT — Solana</option>
            <option value="BNBUSDT">BNBUSDT — BNB</option>
            <option value="XRPUSDT">XRPUSDT — Ripple</option>
            <option value="DOGEUSDT">DOGEUSDT — Dogecoin</option>
            <option value="AVAXUSDT">AVAXUSDT — Avalanche</option>
            <option value="ADAUSDT">ADAUSDT — Cardano</option>
            <option value="DOTUSDT">DOTUSDT — Polkadot</option>
            <option value="MATICUSDT">MATICUSDT — Polygon</option>
            <option value="LINKUSDT">LINKUSDT — Chainlink</option>
            <option value="NEARUSDT">NEARUSDT — NEAR</option>
            <option value="AAVEUSDT">AAVEUSDT — Aave</option>
            <option value="UNIUSDT">UNIUSDT — Uniswap</option>
            <option value="ARBUSDT">ARBUSDT — Arbitrum</option>
          </optgroup>
          <optgroup label={isRu ? "Форекс" : "Forex"}>
            <option value="EURUSD">EURUSD — {isRu ? "Евро/Доллар" : "Euro/Dollar"}</option>
            <option value="GBPUSD">GBPUSD — {isRu ? "Фунт/Доллар" : "Pound/Dollar"}</option>
            <option value="USDJPY">USDJPY — {isRu ? "Доллар/Иена" : "Dollar/Yen"}</option>
            <option value="USDCHF">USDCHF — {isRu ? "Доллар/Франк" : "Dollar/Franc"}</option>
            <option value="AUDUSD">AUDUSD — {isRu ? "Австрал./Доллар" : "AUD/Dollar"}</option>
            <option value="USDCAD">USDCAD — {isRu ? "Доллар/Канад." : "Dollar/CAD"}</option>
            <option value="EURGBP">EURGBP — {isRu ? "Евро/Фунт" : "Euro/Pound"}</option>
            <option value="EURJPY">EURJPY — {isRu ? "Евро/Иена" : "Euro/Yen"}</option>
            <option value="GBPJPY">GBPJPY — {isRu ? "Фунт/Иена" : "Pound/Yen"}</option>
          </optgroup>
          <optgroup label={isRu ? "Акции US" : "US Stocks"}>
            <option value="AAPL">AAPL — Apple</option>
            <option value="MSFT">MSFT — Microsoft</option>
            <option value="NVDA">NVDA — Nvidia</option>
            <option value="TSLA">TSLA — Tesla</option>
            <option value="GOOGL">GOOGL — Google</option>
            <option value="AMZN">AMZN — Amazon</option>
            <option value="META">META — Meta</option>
          </optgroup>
          <optgroup label={isRu ? "Акции РФ (MOEX)" : "RU Stocks (MOEX)"}>
            <option value="SBER">SBER — {isRu ? "Сбербанк" : "Sberbank"}</option>
            <option value="GAZP">GAZP — {isRu ? "Газпром" : "Gazprom"}</option>
            <option value="LKOH">LKOH — {isRu ? "Лукойл" : "Lukoil"}</option>
            <option value="YNDX">YNDX — {isRu ? "Яндекс" : "Yandex"}</option>
            <option value="GMKN">GMKN — {isRu ? "Норникель" : "Nornickel"}</option>
          </optgroup>
          <optgroup label={isRu ? "Сырьё и индексы" : "Commodities & Indices"}>
            <option value="XAUUSD">XAUUSD — {isRu ? "Золото" : "Gold"}</option>
            <option value="XAGUSD">XAGUSD — {isRu ? "Серебро" : "Silver"}</option>
            <option value="USOIL">USOIL — {isRu ? "Нефть" : "Oil"}</option>
            <option value="SPX500">SPX500 — S&P 500</option>
            <option value="NAS100">NAS100 — Nasdaq 100</option>
            <option value="DAX40">DAX40 — DAX</option>
          </optgroup>
        </select>
        <div className="flex gap-1">
          {STATUS_FILTERS.map((f) => (
            <button key={f.value} onClick={() => setStatusFilter(f.value)} className={`rounded-lg px-3 py-2 text-sm transition ${statusFilter === f.value ? "bg-brand-500/20 text-brand-500" : "text-text-secondary hover:bg-surface-hover hover:text-text-primary"}`}>{f.label}</button>
          ))}
        </div>
      </div>

      <div className="mb-4 rounded-lg border border-yellow-500/20 bg-yellow-500/5 px-4 py-2">
        <p className="text-xs text-yellow-400/80">{t("signals.disclaimer")}</p>
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>
      ) : signals.length === 0 ? (
        <div className="rounded-xl border border-border bg-surface-card p-12 text-center">
          <p className="text-text-secondary">{t("signals.empty")}</p>
          <p className="mt-1 text-sm text-text-muted">{t("signals.emptyHint")}</p>
        </div>
      ) : (
        <div className="space-y-3">{signals.map((s) => {
          const ev = evaluations[s.id];
          return (
            <SignalCard
              key={s.id}
              signal={s}
              strategyLabel={isPremium && ev ? (isRu ? ev.strategy_name_ru : ev.strategy_name) : undefined}
              regimeLabel={isPremium && ev ? (isRu ? (REGIME_RU[ev.regime] || ev.regime) : ev.regime?.replace("_", " ")) : undefined}
            />
          );
        })}</div>
      )}
    </div>
  );
}
