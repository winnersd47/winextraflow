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
  const [statusFilter, setStatusFilter] = useState("");
  const [tickerFilter, setTickerFilter] = useState("");
  const { t } = useI18n();

  const fetchSignals = useCallback(async () => {
    try {
      const data = await api.getSignals({
        status: statusFilter || undefined,
        ticker: tickerFilter || undefined,
        limit: 50,
      });
      setSignals(data.items);
      setTotal(data.total);
    } catch (err) {
      console.error("Failed to fetch signals:", err);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, tickerFilter]);

  useEffect(() => { fetchSignals(); }, [fetchSignals]);

  const handleNewSignal = useCallback((_msg: WSNewSignal) => { fetchSignals(); }, [fetchSignals]);
  const { connected } = useWebSocket(handleNewSignal);

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
          <h1 className="text-2xl font-bold text-white">{t("signals.title")}</h1>
          <p className="text-sm text-gray-400">
            {total} {t("signals.total")}{" "}
            <span className={`ml-2 inline-block h-2 w-2 rounded-full ${connected ? "bg-green-500" : "bg-red-500"}`} />
            <span className="ml-1 text-xs">{connected ? t("signals.live") : t("signals.reconnecting")}</span>
          </p>
        </div>
      </div>
      <div className="mb-4 flex flex-wrap gap-3">
        <input type="text" placeholder={t("signals.filterTicker")} value={tickerFilter} onChange={(e) => setTickerFilter(e.target.value)} className="rounded-lg border border-gray-700 bg-surface px-3 py-2 text-sm text-white outline-none focus:border-brand-500" />
        <div className="flex gap-1">
          {STATUS_FILTERS.map((f) => (
            <button key={f.value} onClick={() => setStatusFilter(f.value)} className={`rounded-lg px-3 py-2 text-sm transition ${statusFilter === f.value ? "bg-brand-500/20 text-brand-500" : "text-gray-400 hover:bg-surface-hover hover:text-white"}`}>{f.label}</button>
          ))}
        </div>
      </div>
      {loading ? (
        <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>
      ) : signals.length === 0 ? (
        <div className="rounded-xl border border-gray-800 bg-surface-card p-12 text-center">
          <p className="text-gray-400">{t("signals.empty")}</p>
          <p className="mt-1 text-sm text-gray-500">{t("signals.emptyHint")}</p>
        </div>
      ) : (
        <div className="space-y-3">{signals.map((s) => <SignalCard key={s.id} signal={s} />)}</div>
      )}
    </div>
  );
}
