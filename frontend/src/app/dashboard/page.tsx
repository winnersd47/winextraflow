"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useWebSocket } from "@/lib/ws";
import { useI18n } from "@/lib/i18n";
import { SignalCard } from "@/components/signal-card";
import type { Signal, WSNewSignal } from "@/types";

export default function DashboardPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const [tickerFilter, setTickerFilter] = useState("");
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const { t } = useI18n();

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
      <div className="mb-6 flex items-center justify-between">
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
        {/* Manual refresh button */}
        <button
          onClick={handleManualRefresh}
          disabled={refreshing}
          className="flex items-center gap-2 rounded-lg border border-border bg-surface-card px-4 py-2 text-sm font-medium text-text-primary transition hover:bg-surface-hover disabled:opacity-50"
        >
          <svg
            className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
            <path d="M3 3v5h5" />
            <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
            <path d="M16 16h5v5" />
          </svg>
          {refreshing ? t("signals.refreshing") : t("signals.refresh")}
        </button>
      </div>
      <div className="mb-4 flex flex-wrap gap-3">
        <input type="text" placeholder={t("signals.filterTicker")} value={tickerFilter} onChange={(e) => setTickerFilter(e.target.value)} className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-500" />
        <div className="flex gap-1">
          {STATUS_FILTERS.map((f) => (
            <button key={f.value} onClick={() => setStatusFilter(f.value)} className={`rounded-lg px-3 py-2 text-sm transition ${statusFilter === f.value ? "bg-brand-500/20 text-brand-500" : "text-text-secondary hover:bg-surface-hover hover:text-text-primary"}`}>{f.label}</button>
          ))}
        </div>
      </div>

      {/* Disclaimer banner */}
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
        <div className="space-y-3">{signals.map((s) => <SignalCard key={s.id} signal={s} />)}</div>
      )}
    </div>
  );
}
