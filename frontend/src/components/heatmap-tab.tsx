"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";
import { CustomHeatmap } from "./heatmap-widget";

// All three markets now come from /api/v1/public/heatmap, which is built from
// sources the platform already uses (MOEX ISS, CoinGecko, Yahoo). The TradingView
// heatmap widget was dropped: its terms require a visible attribution link.
type HeatmapView = "moex" | "crypto" | "us";

export default function HeatmapTab() {
  const [view, setView] = useState<HeatmapView>("moex");
  const [moexData, setMoexData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const { locale } = useI18n();
  const isRu = locale === "ru";

  useEffect(() => {
    let alive = true;
    setLoading(true);
    fetch(`/api/v1/public/heatmap?market=${view}`)
      .then(r => (r.ok ? r.json() : null))
      .then(d => { if (alive && d?.tickers) setMoexData(d.tickers); })
      .catch(() => {})
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [view]);

  const VIEWS: { key: HeatmapView; ru: string; en: string; src: string }[] = [
    { key: "moex", ru: "MOEX", en: "MOEX", src: "MOEX ISS API" },
    { key: "crypto", ru: "Крипто", en: "Crypto", src: "CoinGecko" },
    { key: "us", ru: "Акции США", en: "US Stocks", src: "Yahoo Finance" },
  ];
  const current = VIEWS.find(v => v.key === view) ?? VIEWS[0];

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-text-primary">
          {isRu ? "Тепловая карта рынка" : "Market Heatmap"}
        </h1>
        <p className="text-sm text-text-secondary">
          {isRu ? "Визуальное отображение динамики по секторам и тикерам" : "Visual display of market dynamics by sector and ticker"}
        </p>
      </div>

      {/* View selector */}
      <div className="mb-4 flex flex-wrap gap-2">
        {VIEWS.map(v => (
          <button key={v.key} onClick={() => setView(v.key)}
            className={`rounded-lg px-3 py-2 text-xs font-medium transition ${view === v.key ? "bg-brand-500 text-white" : "text-text-secondary hover:bg-surface-hover"}`}>
            {isRu ? v.ru : v.en}
          </button>
        ))}
      </div>

      <div className="rounded-xl border border-border bg-surface-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="font-bold text-text-primary">
            {isRu ? current.ru : current.en}
          </h3>
          <div className="flex items-center gap-2">
            <span className="pulse-dot" />
            <span className="text-xs text-text-muted">{current.src}</span>
          </div>
        </div>
        {loading ? (
          <div className="flex justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
          </div>
        ) : moexData.length ? (
          <CustomHeatmap data={moexData} isRu={isRu} />
        ) : (
          <p className="py-10 text-center text-sm text-text-muted">
            {isRu ? "Данные недоступны — источник не ответил." : "No data — the source did not respond."}
          </p>
        )}
        <p className="mt-3 text-xs text-text-muted">
          {isRu
            ? "Размер блока — объём торгов, цвет — изменение за день. Тикер без котировки не показывается вовсе, а не нулём."
            : "Block size is volume, colour is the daily change. A ticker without a quote is omitted rather than shown as zero."}
        </p>
      </div>

      {/* Disclaimer */}
      <div className="mt-4 rounded-lg border border-yellow-500/20 bg-yellow-500/5 px-4 py-2">
        <p className="text-xs text-yellow-400/80">
          {isRu
            ? "Данные носят информационный характер. Не является инвестиционной рекомендацией."
            : "Data is for informational purposes. Not investment advice."}
        </p>
      </div>
    </div>
  );
}
