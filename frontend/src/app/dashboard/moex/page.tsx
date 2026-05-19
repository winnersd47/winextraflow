"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";

export default function MoexPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const { locale } = useI18n();
  const isRu = locale === "ru";

  const load = async (showSpinner = false) => {
    if (showSpinner) setRefreshing(true);
    try {
      const token = localStorage.getItem("token");
      const resp = await fetch("/api/v1/moex/overview", { headers: { Authorization: `Bearer ${token}` } });
      if (resp.ok) { setData(await resp.json()); setLastUpdate(new Date()); }
    } catch {}
    finally { setLoading(false); setRefreshing(false); }
  };

  useEffect(() => {
    load();
    const interval = setInterval(() => load(), 60_000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;
  if (!data) return <div className="py-20 text-center text-text-muted">{isRu ? "Не удалось загрузить данные MOEX" : "Failed to load MOEX data"}</div>;

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">{isRu ? "Московская биржа" : "Moscow Exchange"}</h1>
          <p className="text-sm text-text-secondary">
            {isRu ? "Котировки в реальном времени через MOEX ISS API" : "Real-time quotes via MOEX ISS API"}
            {lastUpdate && <span className="ml-3 text-xs text-text-muted">{isRu ? "Обновлено" : "Updated"}: {lastUpdate.toLocaleTimeString()}</span>}
          </p>
        </div>
        <button onClick={() => load(true)} disabled={refreshing}
          className="flex items-center gap-2 rounded-lg border border-border bg-surface-card px-4 py-2 text-sm text-text-primary hover:bg-surface-hover disabled:opacity-50">
          <svg className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" /><path d="M3 3v5h5" />
            <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" /><path d="M16 16h5v5" />
          </svg>
          {refreshing ? "..." : (isRu ? "Обновить" : "Refresh")}
        </button>
      </div>

      {/* Indices */}
      {data.indices?.length > 0 && (
        <div className="mb-6 grid gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {data.indices.map((idx: any) => (
            <div key={idx.ticker} className="rounded-xl border border-border bg-surface-card p-4">
              <p className="text-xs text-text-muted">{idx.name}</p>
              <p className="text-xl font-bold text-text-primary">{idx.value?.toLocaleString("ru-RU", { maximumFractionDigits: 2 })}</p>
              <p className={`text-sm font-bold ${(idx.change_pct || 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                {(idx.change_pct || 0) >= 0 ? "+" : ""}{idx.change_pct?.toFixed(2)}%
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Top Movers */}
      <div className="mb-6 grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-border bg-surface-card p-4">
          <h3 className="mb-3 font-bold text-green-400">{isRu ? "Лидеры роста" : "Top Gainers"}</h3>
          {(data.top_gainers || []).map((q: any) => (
            <div key={q.ticker} className="flex items-center justify-between py-1.5 border-b border-border last:border-0">
              <div>
                <span className="text-sm font-bold text-text-primary">{q.ticker}</span>
                <span className="ml-2 text-xs text-text-muted">{q.name}</span>
              </div>
              <div className="text-right">
                <span className="text-sm text-text-primary">{q.price?.toLocaleString("ru-RU")}</span>
                <span className="ml-2 text-xs font-bold text-green-400">+{q.change_pct?.toFixed(2)}%</span>
              </div>
            </div>
          ))}
        </div>
        <div className="rounded-xl border border-border bg-surface-card p-4">
          <h3 className="mb-3 font-bold text-red-400">{isRu ? "Лидеры падения" : "Top Losers"}</h3>
          {(data.top_losers || []).map((q: any) => (
            <div key={q.ticker} className="flex items-center justify-between py-1.5 border-b border-border last:border-0">
              <div>
                <span className="text-sm font-bold text-text-primary">{q.ticker}</span>
                <span className="ml-2 text-xs text-text-muted">{q.name}</span>
              </div>
              <div className="text-right">
                <span className="text-sm text-text-primary">{q.price?.toLocaleString("ru-RU")}</span>
                <span className="ml-2 text-xs font-bold text-red-400">{q.change_pct?.toFixed(2)}%</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* All Quotes */}
      <div className="rounded-xl border border-border bg-surface-card p-4">
        <h3 className="mb-3 font-bold text-text-primary">{isRu ? "Все котировки" : "All Quotes"} ({data.quotes?.length || 0})</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-text-muted">
              <tr>
                <th className="pb-2 pr-3">{isRu ? "Тикер" : "Ticker"}</th>
                <th className="pb-2 pr-3">{isRu ? "Название" : "Name"}</th>
                <th className="pb-2 pr-3 text-right">{isRu ? "Цена" : "Price"}</th>
                <th className="pb-2 pr-3 text-right">{isRu ? "Изм." : "Change"}</th>
                <th className="pb-2 pr-3 text-right">%</th>
                <th className="pb-2 pr-3 text-right">{isRu ? "Макс" : "High"}</th>
                <th className="pb-2 pr-3 text-right">{isRu ? "Мин" : "Low"}</th>
                <th className="pb-2 text-right">{isRu ? "Объём" : "Volume"}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(data.quotes || []).map((q: any) => (
                <tr key={q.ticker}>
                  <td className="py-2 pr-3 font-bold text-text-primary">{q.ticker}</td>
                  <td className="py-2 pr-3 text-text-secondary">{q.name}</td>
                  <td className="py-2 pr-3 text-right font-medium text-text-primary">{q.price?.toLocaleString("ru-RU")}</td>
                  <td className={`py-2 pr-3 text-right font-bold ${(q.change || 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                    {(q.change || 0) >= 0 ? "+" : ""}{q.change?.toFixed(2)}
                  </td>
                  <td className={`py-2 pr-3 text-right font-bold ${(q.change_pct || 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                    {(q.change_pct || 0) >= 0 ? "+" : ""}{q.change_pct?.toFixed(2)}%
                  </td>
                  <td className="py-2 pr-3 text-right text-text-muted">{q.high?.toLocaleString("ru-RU")}</td>
                  <td className="py-2 pr-3 text-right text-text-muted">{q.low?.toLocaleString("ru-RU")}</td>
                  <td className="py-2 text-right text-text-muted">{q.volume?.toLocaleString("ru-RU")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="mt-4 rounded-lg bg-surface px-4 py-2 text-xs text-text-muted">
        {isRu
          ? "Данные предоставлены Московской биржей (MOEX ISS API). Котировки могут иметь задержку. Не является инвестиционной рекомендацией."
          : "Data provided by Moscow Exchange (MOEX ISS API). Quotes may be delayed. Not investment advice."}
      </div>
    </div>
  );
}
