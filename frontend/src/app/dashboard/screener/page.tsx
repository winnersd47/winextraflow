"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";

interface ScreenerResult {
  ticker: string;
  market: string;
  total_signals: number;
  active: number;
  buys: number;
  sells: number;
  bias: string;
  bias_pct: number;
  avg_wef_score: number;
  win_rate: number | null;
  avg_profit: number | null;
  latest_action: string;
  latest_price: number;
  latest_tp: number | null;
  latest_sl: number | null;
  latest_at: string | null;
}

const MARKETS = ["all", "MOEX", "Crypto", "Forex", "US Stocks"];
const SORTS = [
  { key: "wef_score", ru: "WEF Score", en: "WEF Score" },
  { key: "signals", ru: "Сигналов", en: "Signals" },
  { key: "win_rate", ru: "Win Rate", en: "Win Rate" },
  { key: "profit", ru: "Прибыль", en: "Profit" },
];

function biasColor(bias: string) {
  if (bias === "bullish") return "text-green-400 bg-green-500/10";
  if (bias === "bearish") return "text-red-400 bg-red-500/10";
  return "text-yellow-400 bg-yellow-500/10";
}

function biasLabel(bias: string, isRu: boolean) {
  if (bias === "bullish") return isRu ? "Бычий" : "Bullish";
  if (bias === "bearish") return isRu ? "Медвежий" : "Bearish";
  return isRu ? "Нейтральный" : "Neutral";
}

function wefColor(score: number) {
  if (score >= 0.8) return "text-green-400";
  if (score >= 0.6) return "text-yellow-400";
  if (score >= 0.4) return "text-orange-400";
  return "text-red-400";
}

export default function ScreenerPage() {
  const [results, setResults] = useState<ScreenerResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [market, setMarket] = useState("all");
  const [sortBy, setSortBy] = useState("wef_score");
  const [action, setAction] = useState("all");
  const [minWef, setMinWef] = useState(0);
  const { locale } = useI18n();
  const isRu = locale === "ru";

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const token = localStorage.getItem("token");
        const params = new URLSearchParams({
          market, sort_by: sortBy, action,
          min_wef_score: minWef.toString(), min_signals: "1",
        });
        const resp = await fetch(`/api/v1/screener/scan?${params}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (resp.ok) {
          const data = await resp.json();
          setResults(data.items || []);
        }
      } catch {}
      finally { setLoading(false); }
    };
    load();
  }, [market, sortBy, action, minWef]);

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-text-primary">
          {isRu ? "Скринер тикеров" : "Ticker Screener"}
        </h1>
        <p className="text-sm text-text-secondary">
          {isRu
            ? `${results.length} тикеров найдено по условиям`
            : `${results.length} tickers match your criteria`}
        </p>
      </div>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        {/* Market */}
        <div className="flex gap-1">
          {MARKETS.map(m => (
            <button key={m} onClick={() => setMarket(m)}
              className={`rounded-lg px-3 py-2 text-xs font-medium transition ${market === m ? "bg-brand-500 text-white" : "text-text-secondary hover:bg-surface-hover"}`}>
              {m === "all" ? (isRu ? "Все" : "All") : m}
            </button>
          ))}
        </div>

        {/* Action */}
        <div className="flex gap-1">
          {[
            { key: "all", label: isRu ? "Все" : "All" },
            { key: "buy", label: "BUY" },
            { key: "sell", label: "SELL" },
          ].map(a => (
            <button key={a.key} onClick={() => setAction(a.key)}
              className={`rounded-lg px-3 py-2 text-xs font-medium transition ${action === a.key ? "bg-brand-500 text-white" : "text-text-secondary hover:bg-surface-hover"}`}>
              {a.label}
            </button>
          ))}
        </div>

        {/* Min WEF */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted">Min WEF:</span>
          <select value={minWef} onChange={e => setMinWef(Number(e.target.value))}
            className="rounded-lg border border-border bg-surface px-2 py-1.5 text-xs text-text-primary">
            <option value={0}>0%</option>
            <option value={0.4}>40%+</option>
            <option value={0.6}>60%+</option>
            <option value={0.8}>80%+</option>
          </select>
        </div>

        {/* Sort */}
        <select value={sortBy} onChange={e => setSortBy(e.target.value)}
          className="rounded-lg border border-border bg-surface px-3 py-2 text-xs text-text-primary">
          {SORTS.map(s => (
            <option key={s.key} value={s.key}>{isRu ? s.ru : s.en}</option>
          ))}
        </select>
      </div>

      {/* Results table */}
      {loading ? (
        <div className="flex justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
        </div>
      ) : results.length === 0 ? (
        <div className="rounded-xl border border-border bg-surface-card p-8 text-center">
          <p className="text-text-muted">{isRu ? "Нет тикеров по заданным условиям" : "No tickers match your criteria"}</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-surface-card text-left text-xs text-text-muted">
                <th className="px-4 py-3">{isRu ? "Тикер" : "Ticker"}</th>
                <th className="px-3 py-3">{isRu ? "Рынок" : "Market"}</th>
                <th className="px-3 py-3">{isRu ? "Уклон" : "Bias"}</th>
                <th className="px-3 py-3 text-center">WEF</th>
                <th className="px-3 py-3 text-center">{isRu ? "Сигналов" : "Signals"}</th>
                <th className="px-3 py-3 text-center">Win Rate</th>
                <th className="px-3 py-3 text-center">{isRu ? "Ср. прибыль" : "Avg Profit"}</th>
                <th className="px-3 py-3">{isRu ? "Последний" : "Latest"}</th>
              </tr>
            </thead>
            <tbody>
              {results.map(r => (
                <tr key={r.ticker} className="border-b border-border/50 hover:bg-surface-hover transition">
                  <td className="px-4 py-3">
                    <span className="font-bold text-text-primary">{r.ticker}</span>
                    {r.active > 0 && (
                      <span className="ml-2 rounded bg-blue-500/10 px-1.5 py-0.5 text-xs text-blue-400">
                        {r.active} {isRu ? "акт." : "active"}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-3 text-xs text-text-muted">{r.market}</td>
                  <td className="px-3 py-3">
                    <span className={`rounded px-2 py-0.5 text-xs font-medium ${biasColor(r.bias)}`}>
                      {biasLabel(r.bias, isRu)}
                    </span>
                  </td>
                  <td className={`px-3 py-3 text-center font-bold ${wefColor(r.avg_wef_score)}`}>
                    {(r.avg_wef_score * 100).toFixed(0)}%
                  </td>
                  <td className="px-3 py-3 text-center text-text-secondary">
                    {r.total_signals}
                    <span className="text-xs text-text-muted ml-1">
                      ({r.buys}B/{r.sells}S)
                    </span>
                  </td>
                  <td className="px-3 py-3 text-center">
                    {r.win_rate !== null ? (
                      <span className={r.win_rate >= 0.6 ? "text-green-400 font-medium" : "text-text-secondary"}>
                        {(r.win_rate * 100).toFixed(0)}%
                      </span>
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </td>
                  <td className="px-3 py-3 text-center">
                    {r.avg_profit !== null ? (
                      <span className={r.avg_profit >= 0 ? "text-green-400" : "text-red-400"}>
                        {r.avg_profit >= 0 ? "+" : ""}{r.avg_profit.toFixed(1)}%
                      </span>
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </td>
                  <td className="px-3 py-3">
                    <span className={`text-xs font-bold ${r.latest_action === "buy" ? "text-green-400" : "text-red-400"}`}>
                      {r.latest_action.toUpperCase()}
                    </span>
                    <span className="ml-1 text-xs text-text-muted">{r.latest_price}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Disclaimer */}
      <div className="mt-4 rounded-lg border border-yellow-500/20 bg-yellow-500/5 px-4 py-2">
        <p className="text-xs text-yellow-400/80">
          {isRu
            ? "Скринер показывает статистику сигналов на платформе. Не является инвестиционной рекомендацией. Прошлые результаты НЕ гарантируют будущую доходность."
            : "Screener shows platform signal statistics. Not investment advice. Past performance does NOT guarantee future returns."}
        </p>
      </div>
    </div>
  );
}
