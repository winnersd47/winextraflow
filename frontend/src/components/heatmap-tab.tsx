"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";
import { TradingViewHeatmap, CustomHeatmap } from "./heatmap-widget";

type HeatmapView = "moex-custom" | "moex-tv" | "crypto-tv" | "us-tv";

export default function HeatmapTab() {
  const [view, setView] = useState<HeatmapView>("moex-custom");
  const [moexData, setMoexData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const { locale } = useI18n();
  const isRu = locale === "ru";

  useEffect(() => {
    if (view !== "moex-custom") return;
    setLoading(true);
    const token = localStorage.getItem("token");
    fetch("/api/v1/moex/heatmap", { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.tickers) setMoexData(d.tickers); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [view]);

  const VIEWS: { key: HeatmapView; ru: string; en: string }[] = [
    { key: "moex-custom", ru: "MOEX (Live)", en: "MOEX (Live)" },
    { key: "moex-tv", ru: "MOEX (TradingView)", en: "MOEX (TradingView)" },
    { key: "crypto-tv", ru: "Крипто", en: "Crypto" },
    { key: "us-tv", ru: "US Stocks (S&P 500)", en: "US Stocks (S&P 500)" },
  ];

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

      {/* MOEX Custom Heatmap (our data) */}
      {view === "moex-custom" && (
        <div className="rounded-xl border border-border bg-surface-card p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-bold text-text-primary">
              {isRu ? "Московская биржа — Live данные" : "Moscow Exchange — Live Data"}
            </h3>
            <div className="flex items-center gap-2">
              <span className="pulse-dot" />
              <span className="text-xs text-text-muted">MOEX ISS API</span>
            </div>
          </div>
          {loading ? (
            <div className="flex justify-center py-12">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
            </div>
          ) : (
            <CustomHeatmap data={moexData} isRu={isRu} />
          )}
          <p className="mt-3 text-xs text-text-muted">
            {isRu
              ? "Данные в реальном времени с MOEX ISS API. Размер блока — объём торгов. Цвет — изменение за день."
              : "Real-time data from MOEX ISS API. Block size — trading volume. Color — daily change."}
          </p>
        </div>
      )}

      {/* TradingView Widgets */}
      {view === "moex-tv" && (
        <div>
          <p className="mb-2 text-xs text-text-muted">
            {isRu ? "TradingView виджет — интерактивная карта MOEX" : "TradingView widget — interactive MOEX heatmap"}
          </p>
          <TradingViewHeatmap market="moex" height={550} />
        </div>
      )}

      {view === "crypto-tv" && (
        <div>
          <p className="mb-2 text-xs text-text-muted">
            {isRu ? "Тепловая карта крипторынка — по капитализации и изменению" : "Crypto market heatmap — by market cap and change"}
          </p>
          <TradingViewHeatmap market="crypto" height={550} />
        </div>
      )}

      {view === "us-tv" && (
        <div>
          <p className="mb-2 text-xs text-text-muted">
            {isRu ? "S&P 500 — акции США по секторам" : "S&P 500 — US stocks by sector"}
          </p>
          <TradingViewHeatmap market="us" height={550} />
        </div>
      )}

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
