"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { formatPercent } from "@/lib/utils";
import type { BacktestResult } from "@/types";

export default function BacktestPage() {
  const [providerId, setProviderId] = useState("");
  const [ticker, setTicker] = useState("");
  const [capital, setCapital] = useState("10000");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState("");

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    setResult(null);
    try {
      const data = await api.runBacktest({
        provider_id: providerId || undefined,
        ticker: ticker || undefined,
        initial_capital: parseFloat(capital) || 10000,
      });
      setResult(data);
    } catch (err: any) {
      setError(err.message || "Backtest failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-2 text-2xl font-bold text-white">Backtesting</h1>
      <p className="mb-6 text-sm text-gray-400">
        Test signal performance on historical data
      </p>

      {/* Form */}
      <form
        onSubmit={handleRun}
        className="mb-6 flex flex-wrap gap-3 rounded-xl border border-gray-800 bg-surface-card p-4"
      >
        <input
          type="text"
          placeholder="Provider ID (optional)"
          value={providerId}
          onChange={(e) => setProviderId(e.target.value)}
          className="flex-1 rounded-lg border border-gray-700 bg-surface px-3 py-2 text-sm text-white outline-none focus:border-brand-500"
        />
        <input
          type="text"
          placeholder="Ticker (optional)"
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          className="w-32 rounded-lg border border-gray-700 bg-surface px-3 py-2 text-sm text-white outline-none focus:border-brand-500"
        />
        <input
          type="number"
          placeholder="Capital"
          value={capital}
          onChange={(e) => setCapital(e.target.value)}
          className="w-32 rounded-lg border border-gray-700 bg-surface px-3 py-2 text-sm text-white outline-none focus:border-brand-500"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-brand-600 px-6 py-2 text-sm font-medium text-white transition hover:bg-brand-700 disabled:opacity-50"
        >
          {loading ? "Running..." : "Run Backtest"}
        </button>
      </form>

      {error && (
        <div className="mb-4 rounded-lg bg-red-500/10 p-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <MetricCard
              label="Total Return"
              value={formatPercent(result.total_return_pct)}
              color={result.total_return_pct >= 0 ? "text-green-400" : "text-red-400"}
            />
            <MetricCard
              label="Win Rate"
              value={`${(result.win_rate * 100).toFixed(1)}%`}
              color={result.win_rate >= 0.5 ? "text-green-400" : "text-red-400"}
            />
            <MetricCard
              label="Sharpe Ratio"
              value={result.sharpe_ratio?.toFixed(2) ?? "N/A"}
              color={
                result.sharpe_ratio !== null && result.sharpe_ratio >= 1
                  ? "text-green-400"
                  : "text-yellow-400"
              }
            />
            <MetricCard
              label="Max Drawdown"
              value={`${result.max_drawdown_pct.toFixed(1)}%`}
              color="text-red-400"
            />
          </div>

          {/* Detailed Metrics */}
          <div className="rounded-xl border border-gray-800 bg-surface-card p-6">
            <h2 className="mb-4 text-lg font-bold text-white">
              Performance Details
            </h2>
            <div className="grid grid-cols-2 gap-y-3 text-sm sm:grid-cols-3">
              <Detail label="Closed Trades" value={String(result.closed_signals)} />
              <Detail label="Active Signals" value={String(result.active_signals)} />
              <Detail label="Expired" value={String(result.expired_signals)} />
              <Detail label="Avg Win" value={formatPercent(result.avg_profit_pct)} />
              <Detail label="Avg Loss" value={formatPercent(result.avg_loss_pct)} />
              <Detail label="Best Trade" value={formatPercent(result.best_trade_pct)} />
              <Detail label="Worst Trade" value={formatPercent(result.worst_trade_pct)} />
              <Detail label="Profit Factor" value={result.profit_factor?.toFixed(2) ?? "N/A"} />
              <Detail label="Max Win Streak" value={String(result.max_consecutive_wins)} />
              <Detail label="Max Loss Streak" value={String(result.max_consecutive_losses)} />
            </div>
          </div>

          {/* Equity Curve */}
          {result.equity_curve.length > 1 && (
            <div className="rounded-xl border border-gray-800 bg-surface-card p-6">
              <h2 className="mb-4 text-lg font-bold text-white">
                Equity Curve
              </h2>
              <div className="flex h-48 items-end gap-px">
                {result.equity_curve.map((val, i) => {
                  const min = Math.min(...result.equity_curve);
                  const max = Math.max(...result.equity_curve);
                  const range = max - min || 1;
                  const height = ((val - min) / range) * 100;
                  const isLast = i === result.equity_curve.length - 1;
                  return (
                    <div
                      key={i}
                      className={`flex-1 rounded-t ${
                        val >= result.equity_curve[0]
                          ? "bg-green-500/60"
                          : "bg-red-500/60"
                      } ${isLast ? "opacity-100" : "opacity-80"}`}
                      style={{ height: `${Math.max(2, height)}%` }}
                      title={`$${val.toFixed(0)}`}
                    />
                  );
                })}
              </div>
              <div className="mt-2 flex justify-between text-xs text-gray-500">
                <span>${result.equity_curve[0]?.toFixed(0)}</span>
                <span>
                  ${result.equity_curve[result.equity_curve.length - 1]?.toFixed(0)}
                </span>
              </div>
            </div>
          )}

          {/* Trades Table */}
          <div className="rounded-xl border border-gray-800 bg-surface-card p-6">
            <h2 className="mb-4 text-lg font-bold text-white">
              Trades ({result.trades.length})
            </h2>
            <div className="max-h-96 overflow-y-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-gray-700 text-gray-400">
                  <tr>
                    <th className="pb-2">Ticker</th>
                    <th className="pb-2">Action</th>
                    <th className="pb-2">Entry</th>
                    <th className="pb-2">Close</th>
                    <th className="pb-2">Profit</th>
                    <th className="pb-2">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {result.trades.map((trade) => (
                    <tr key={trade.signal_id} className="text-gray-300">
                      <td className="py-2 font-medium text-white">
                        {trade.ticker}
                      </td>
                      <td
                        className={`py-2 uppercase ${
                          trade.action === "buy"
                            ? "text-green-400"
                            : "text-red-400"
                        }`}
                      >
                        {trade.action}
                      </td>
                      <td className="py-2">{trade.entry_price}</td>
                      <td className="py-2">{trade.close_price}</td>
                      <td
                        className={`py-2 font-medium ${
                          trade.profit_pct >= 0
                            ? "text-green-400"
                            : "text-red-400"
                        }`}
                      >
                        {formatPercent(trade.profit_pct)}
                      </td>
                      <td className="py-2 text-gray-400">{trade.status}</td>
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

function MetricCard({
  label,
  value,
  color = "text-white",
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="rounded-xl border border-gray-800 bg-surface-card p-4">
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${color}`}>{value}</p>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-gray-500">{label}: </span>
      <span className="font-medium text-white">{value}</span>
    </div>
  );
}
