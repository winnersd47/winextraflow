"use client";


interface Props {
  market: "moex" | "crypto" | "us" | "world";
  height?: number;
  colorTheme?: "dark" | "light";
}

/**
 * TradingView Stock/Crypto Heatmap Widget (free, no API key).
 * Embeds official TradingView widget via iframe script.
 */
// TradingViewHeatmap removed: the widget's terms require a visible attribution
// link, and all three markets are now served by /api/v1/public/heatmap from
// sources the platform already calls (MOEX ISS, CoinGecko, Yahoo).

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
