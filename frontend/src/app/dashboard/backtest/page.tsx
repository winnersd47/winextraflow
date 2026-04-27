"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const EquityChart = dynamic(() => import("@/components/equity-chart").then(m => ({ default: m.EquityChart })), { ssr: false });
import { formatPercent } from "@/lib/utils";
import type { BacktestResult } from "@/types";

export default function BacktestPage() {
  const [providerId, setProviderId] = useState("");
  const [ticker, setTicker] = useState("");
  const [capital, setCapital] = useState("10000");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState("");
  const { t } = useI18n();

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    setResult(null);
    try {
      setResult(await api.runBacktest({ provider_id: providerId || undefined, ticker: ticker || undefined, initial_capital: parseFloat(capital) || 10000 }));
    } catch (err: any) { setError(err.message || "Backtest failed"); }
    finally { setLoading(false); }
  };

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-2 text-2xl font-bold text-white">{t("backtest.title")}</h1>
      <p className="mb-6 text-sm text-gray-400">{t("backtest.subtitle")}</p>

      <form onSubmit={handleRun} className="mb-6 flex flex-wrap gap-3 rounded-xl border border-gray-800 bg-surface-card p-4">
        <input type="text" placeholder={t("backtest.providerId")} value={providerId} onChange={(e) => setProviderId(e.target.value)} className="flex-1 rounded-lg border border-gray-700 bg-surface px-3 py-2 text-sm text-white outline-none focus:border-brand-500" />
        <input type="text" placeholder={t("backtest.ticker")} value={ticker} onChange={(e) => setTicker(e.target.value)} className="w-32 rounded-lg border border-gray-700 bg-surface px-3 py-2 text-sm text-white outline-none focus:border-brand-500" />
        <input type="number" placeholder={t("backtest.capital")} value={capital} onChange={(e) => setCapital(e.target.value)} className="w-32 rounded-lg border border-gray-700 bg-surface px-3 py-2 text-sm text-white outline-none focus:border-brand-500" />
        <button type="submit" disabled={loading} className="rounded-lg bg-brand-600 px-6 py-2 text-sm font-medium text-white transition hover:bg-brand-700 disabled:opacity-50">{loading ? t("backtest.running") : t("backtest.run")}</button>
      </form>

      {error && <div className="mb-4 rounded-lg bg-red-500/10 p-3 text-sm text-red-400">{error}</div>}

      {result && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <MC label={t("backtest.totalReturn")} value={formatPercent(result.total_return_pct)} color={result.total_return_pct >= 0 ? "text-green-400" : "text-red-400"} />
            <MC label={t("backtest.winRate")} value={`${(result.win_rate * 100).toFixed(1)}%`} color={result.win_rate >= 0.5 ? "text-green-400" : "text-red-400"} />
            <MC label={t("backtest.sharpe")} value={result.sharpe_ratio?.toFixed(2) ?? "N/A"} color={result.sharpe_ratio !== null && result.sharpe_ratio >= 1 ? "text-green-400" : "text-yellow-400"} />
            <MC label={t("backtest.maxDrawdown")} value={`${result.max_drawdown_pct.toFixed(1)}%`} color="text-red-400" />
          </div>

          <div className="rounded-xl border border-gray-800 bg-surface-card p-6">
            <h2 className="mb-4 text-lg font-bold text-white">{t("backtest.details")}</h2>
            <div className="grid grid-cols-2 gap-y-3 text-sm sm:grid-cols-3">
              <D label={t("backtest.closedTrades")} value={String(result.closed_signals)} />
              <D label={t("backtest.activeSignals")} value={String(result.active_signals)} />
              <D label={t("backtest.expiredLabel")} value={String(result.expired_signals)} />
              <D label={t("backtest.avgWin")} value={formatPercent(result.avg_profit_pct)} />
              <D label={t("backtest.avgLoss")} value={formatPercent(result.avg_loss_pct)} />
              <D label={t("backtest.bestTrade")} value={formatPercent(result.best_trade_pct)} />
              <D label={t("backtest.worstTrade")} value={formatPercent(result.worst_trade_pct)} />
              <D label={t("backtest.profitFactor")} value={result.profit_factor?.toFixed(2) ?? "N/A"} />
              <D label={t("backtest.maxWinStreak")} value={String(result.max_consecutive_wins)} />
              <D label={t("backtest.maxLossStreak")} value={String(result.max_consecutive_losses)} />
            </div>
          </div>

          {result.equity_curve.length > 1 && (
            <div className="rounded-xl border border-border bg-surface-card p-6">
              <h2 className="mb-4 text-lg font-bold text-text-primary">{t("backtest.equityCurve")}</h2>
              <EquityChart data={result.equity_curve} initialCapital={parseFloat(capital) || 10000} />
            </div>
          )}

          <div className="rounded-xl border border-gray-800 bg-surface-card p-6">
            <h2 className="mb-4 text-lg font-bold text-white">{t("backtest.trades")} ({result.trades.length})</h2>
            <div className="max-h-96 overflow-y-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-gray-700 text-gray-400">
                  <tr><th className="pb-2">Ticker</th><th className="pb-2">Action</th><th className="pb-2">{t("signals.entry")}</th><th className="pb-2">Close</th><th className="pb-2">Profit</th><th className="pb-2">{t("signals.status")}</th></tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {result.trades.map((tr) => (
                    <tr key={tr.signal_id} className="text-gray-300">
                      <td className="py-2 font-medium text-white">{tr.ticker}</td>
                      <td className={`py-2 uppercase ${tr.action === "buy" ? "text-green-400" : "text-red-400"}`}>{tr.action}</td>
                      <td className="py-2">{tr.entry_price}</td>
                      <td className="py-2">{tr.close_price}</td>
                      <td className={`py-2 font-medium ${tr.profit_pct >= 0 ? "text-green-400" : "text-red-400"}`}>{formatPercent(tr.profit_pct)}</td>
                      <td className="py-2 text-gray-400">{tr.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function MC({ label, value, color = "text-white" }: { label: string; value: string; color?: string }) {
  return <div className="rounded-xl border border-gray-800 bg-surface-card p-4"><p className="text-xs text-gray-500">{label}</p><p className={`mt-1 text-2xl font-bold ${color}`}>{value}</p></div>;
}
function D({ label, value }: { label: string; value: string }) {
  return <div><span className="text-gray-500">{label}: </span><span className="font-medium text-white">{value}</span></div>;
}
