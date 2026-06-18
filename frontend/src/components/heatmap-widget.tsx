"use client";

import { useEffect, useRef } from "react";

interface Props {
  market: "moex" | "crypto" | "us" | "world";
  height?: number;
  colorTheme?: "dark" | "light";
}

/**
 * TradingView Stock/Crypto Heatmap Widget (free, no API key).
 * Embeds official TradingView widget via iframe script.
 */
export function TradingViewHeatmap({ market, height = 500, colorTheme = "dark" }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    containerRef.current.innerHTML = "";

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js";
    script.async = true;
    script.type = "text/javascript";

    const config: Record<string, any> = {
      colorTheme,
      hasTopBar: true,
      isDataSetEnabled: true,
      isZoomEnabled: true,
      hasSymbolTooltip: true,
      width: "100%",
      height,
      locale: "ru",
    };

    if (market === "moex") {
      config.exchanges = [];
      config.dataSource = "MOEX";
      config.grouping = "sector";
      config.blockSize = "market_cap_basic";
      config.blockColor = "change";
    } else if (market === "crypto") {
      config.dataSource = "Crypto";
      config.blockSize = "market_cap_calc";
      config.blockColor = "change";
      config.grouping = "no_group";
    } else if (market === "us") {
      config.exchanges = [];
      config.dataSource = "SPX500";
      config.grouping = "sector";
      config.blockSize = "market_cap_basic";
      config.blockColor = "change";
    } else {
      config.exchanges = [];
      config.dataSource = "AllUSA";
      config.grouping = "sector";
      config.blockSize = "market_cap_basic";
      config.blockColor = "change";
    }

    script.innerHTML = JSON.stringify(config);

    const wrapper = document.createElement("div");
    wrapper.className = "tradingview-widget-container";
    wrapper.appendChild(script);
    containerRef.current.appendChild(wrapper);

    return () => {
      if (containerRef.current) containerRef.current.innerHTML = "";
    };
  }, [market, height, colorTheme]);

  return <div ref={containerRef} className="rounded-xl overflow-hidden border border-border" />;
}

/**
 * Custom MOEX Heatmap — built from our own MOEX API data.
 * Shows sectors with color-coded performance boxes.
 */
interface HeatmapTicker {
  ticker: string;
  price: number;
  change_pct: number;
  volume?: number;
  sector?: string;
}

function changeColor(pct: number): string {
  if (pct >= 3) return "bg-green-600";
  if (pct >= 1.5) return "bg-green-500/80";
  if (pct >= 0.5) return "bg-green-500/50";
  if (pct >= 0) return "bg-green-500/20";
  if (pct >= -0.5) return "bg-red-500/20";
  if (pct >= -1.5) return "bg-red-500/50";
  if (pct >= -3) return "bg-red-500/80";
  return "bg-red-600";
}

function changeTextColor(pct: number): string {
  if (pct >= 0.5) return "text-green-100";
  if (pct <= -0.5) return "text-red-100";
  return "text-gray-200";
}

export function CustomHeatmap({ data, isRu }: { data: HeatmapTicker[]; isRu: boolean }) {
  if (!data || data.length === 0) {
    return <p className="text-center text-text-muted py-8">{isRu ? "Нет данных" : "No data"}</p>;
  }

  // Group by sector
  const sectors: Record<string, HeatmapTicker[]> = {};
  for (const t of data) {
    const sec = t.sector || "Other";
    if (!sectors[sec]) sectors[sec] = [];
    sectors[sec].push(t);
  }

  return (
    <div className="space-y-3">
      {Object.entries(sectors).map(([sector, tickers]) => (
        <div key={sector}>
          <h4 className="mb-1 text-xs font-bold text-text-muted uppercase tracking-wider">{sector}</h4>
          <div className="flex flex-wrap gap-1">
            {tickers.sort((a, b) => (b.volume || 0) - (a.volume || 0)).map(t => (
              <div
                key={t.ticker}
                className={`rounded-lg px-3 py-2 min-w-[70px] text-center transition hover:scale-105 cursor-default ${changeColor(t.change_pct)}`}
                title={`${t.ticker}: ${t.price} (${t.change_pct >= 0 ? "+" : ""}${t.change_pct.toFixed(2)}%)`}
              >
                <div className={`text-xs font-bold ${changeTextColor(t.change_pct)}`}>{t.ticker}</div>
                <div className={`text-sm font-extrabold ${changeTextColor(t.change_pct)}`}>
                  {t.change_pct >= 0 ? "+" : ""}{t.change_pct.toFixed(1)}%
                </div>
                <div className="text-xs opacity-60">{t.price}</div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
