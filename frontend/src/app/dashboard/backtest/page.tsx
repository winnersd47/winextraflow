"use client";

import { useEffect, useState } from "react";
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
  const [history, setHistory] = useState<any[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const { t, locale } = useI18n();
  const isRu = locale === "ru";

  const loadHistory = async () => {
    try {
      const token = localStorage.getItem("token");
      const resp = await fetch("/api/v1/backtest/history?limit=10", { headers: { Authorization: `Bearer ${token}` } });
      if (resp.ok) { const d = await resp.json(); setHistory(d.items); }
    } catch {}
    finally { setLoadingHistory(false); }
  };

  useEffect(() => { loadHistory(); }, []);

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    const cap = parseFloat(capital);
    if (!cap || cap <= 0) {
      setError(isRu ? "Капитал должен быть положительным числом" : "Capital must be a positive number");
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      setResult(await api.runBacktest({ provider_id: providerId || undefined, ticker: ticker || undefined, initial_capital: cap }));
      loadHistory();
    } catch (err: any) {
      setError(err.message || "Backtest failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-2 text-2xl font-bold text-text-primary">{t("backtest.title")}</h1>
      <p className="mb-4 text-sm text-text-secondary">{t("backtest.subtitle")}</p>

      {/* Legal disclaimer */}
      <div className="mb-6 rounded-lg border border-yellow-500/20 bg-yellow-500/5 px-4 py-3">
        <p className="text-xs leading-relaxed text-yellow-400/80">
          {isRu
            ? "Результаты бэктестинга основаны на исторических данных и НЕ гарантируют будущую доходность. Прошлые результаты торговли не являются индикатором будущих результатов. Бэктестинг не учитывает проскальзывание, комиссии биржи, ликвидность и рыночные условия реального времени. Используйте результаты исключительно в информационных целях."
            : "Backtesting results are based on historical data and DO NOT guarantee future returns. Past trading performance is not an indicator of future results. Backtesting does not account for slippage, exchange fees, liquidity, and real-time market conditions. Use results for informational purposes only."}
        </p>
      </div>

      <form onSubmit={handleRun} className="mb-6 flex flex-wrap gap-3 rounded-xl border border-border bg-surface-card p-4">
        <input type="text" placeholder={t("backtest.providerId")} value={providerId} onChange={(e) => setProviderId(e.target.value)} className="flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-500" />
        <input type="text" placeholder={t("backtest.ticker")} value={ticker} onChange={(e) => setTicker(e.target.value)} className="w-32 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-500" />
        <input type="number" placeholder={t("backtest.capital")} value={capital} onChange={(e) => setCapital(e.target.value)} min="1" max="100000000" className="w-32 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-500" />
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

          {/* Simulated results warning */}
          <div className="rounded-lg bg-surface px-4 py-2 text-center">
            <p className="text-xs text-text-muted">
              {isRu
                ? "* Результаты симуляции. Реальная торговля может существенно отличаться."
                : "* Simulated results. Actual trading may differ significantly."}
            </p>
          </div>

          <div className="rounded-xl border border-border bg-surface-card p-6">
            <h2 className="mb-4 text-lg font-bold text-text-primary">{t("backtest.details")}</h2>
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
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-lg font-bold text-text-primary">{t("backtest.equityCurve")}</h2>
                <span className="text-xs text-text-muted">
                  {isRu ? "* Гипотетическая кривая, не реальный результат" : "* Hypothetical curve, not actual results"}
                </span>
              </div>
              <EquityChart data={result.equity_curve} initialCapital={parseFloat(capital) || 10000} />
            </div>
          )}

          <div className="rounded-xl border border-border bg-surface-card p-6">
            <h2 className="mb-4 text-lg font-bold text-text-primary">{t("backtest.trades")} ({result.trades.length})</h2>
            <div className="max-h-96 overflow-y-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border text-text-muted">
                  <tr>
                    <th className="pb-2">{isRu ? "Тикер" : "Ticker"}</th>
                    <th className="pb-2">{isRu ? "Действие" : "Action"}</th>
                    <th className="pb-2">{t("signals.entry")}</th>
                    <th className="pb-2">{isRu ? "Закрытие" : "Close"}</th>
                    <th className="pb-2">{isRu ? "Прибыль" : "Profit"}</th>
                    <th className="pb-2">{t("signals.status")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {result.trades.map((tr) => (
                    <tr key={tr.signal_id} className="text-text-secondary">
                      <td className="py-2 font-medium text-text-primary">{tr.ticker}</td>
                      <td className={`py-2 uppercase ${tr.action === "buy" ? "text-green-400" : "text-red-400"}`}>{tr.action}</td>
                      <td className="py-2">{tr.entry_price}</td>
                      <td className="py-2">{tr.close_price}</td>
                      <td className={`py-2 font-medium ${tr.profit_pct >= 0 ? "text-green-400" : "text-red-400"}`}>{formatPercent(tr.profit_pct)}</td>
                      <td className="py-2 text-text-muted">{tr.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Bottom disclaimer */}
          <div className="rounded-lg border border-border bg-surface-card px-4 py-3 text-xs text-text-muted">
            {isRu ? (
              <p>
                Бэктестинг проводится на исторических данных платформы. Результаты не учитывают: комиссии бирж,
                проскальзывание (slippage), спреды, ликвидность рынка, задержки исполнения. Реальная торговля
                сопряжена с существенными рисками, включая полную потерю инвестированных средств.
                Данные результаты НЕ являются инвестиционной рекомендацией и предоставляются исключительно
                в информационных целях в соответствии с политикой использования платформы.
              </p>
            ) : (
              <p>
                Backtesting is conducted on the platform&apos;s historical data. Results do not account for:
                exchange fees, slippage, spreads, market liquidity, execution delays. Real trading involves
                significant risks, including total loss of invested funds. These results are NOT investment
                advice and are provided for informational purposes only in accordance with the platform&apos;s
                usage policy.
              </p>
            )}
          </div>
        </div>
      )}

      {/* ═══ BACKTEST HISTORY ═══ */}
      <div className="mt-8 rounded-xl border border-border bg-surface-card p-6">
        <h2 className="mb-4 text-lg font-bold text-text-primary">
          {isRu ? "История бэктестов" : "Backtest History"} ({history.length})
        </h2>
        {loadingHistory ? (
          <div className="flex justify-center py-4"><div className="h-5 w-5 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>
        ) : history.length === 0 ? (
          <p className="py-4 text-center text-text-muted">{isRu ? "Запустите первый бэктест — результат сохранится здесь." : "Run your first backtest — result will be saved here."}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-text-muted">
                <tr>
                  <th className="pb-2 pr-3">{isRu ? "Отчёт" : "Report"}</th>
                  <th className="pb-2 pr-3 text-right">{isRu ? "Доходность" : "Return"}</th>
                  <th className="pb-2 pr-3 text-right">{isRu ? "Винрейт" : "Win Rate"}</th>
                  <th className="pb-2 pr-3 text-right">Sharpe</th>
                  <th className="pb-2 pr-3 text-right">{isRu ? "Просадка" : "Drawdown"}</th>
                  <th className="pb-2 pr-3 text-right">{isRu ? "Сделок" : "Trades"}</th>
                  <th className="pb-2 text-right">{isRu ? "Дата" : "Date"}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {history.map((r: any) => (
                  <tr key={r.id} className="cursor-pointer hover:bg-surface-hover" onClick={() => {
                    setResult({
                      provider_id: r.provider_id, ticker: r.ticker, date_from: null, date_to: null,
                      total_signals: r.total_signals, closed_signals: r.closed_signals,
                      active_signals: 0, expired_signals: 0,
                      total_return_pct: r.total_return_pct, win_rate: r.win_rate,
                      avg_profit_pct: r.avg_profit_pct, avg_loss_pct: r.avg_loss_pct,
                      best_trade_pct: r.best_trade_pct, worst_trade_pct: r.worst_trade_pct,
                      sharpe_ratio: r.sharpe_ratio, profit_factor: r.profit_factor,
                      max_drawdown_pct: r.max_drawdown_pct,
                      max_consecutive_wins: 0, max_consecutive_losses: 0,
                      trades: [], equity_curve: r.equity_curve || [],
                    });
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }}>
                    <td className="py-2.5 pr-3">
                      <p className="font-medium text-text-primary text-xs">{r.title}</p>
                    </td>
                    <td className={`py-2.5 pr-3 text-right font-bold ${r.total_return_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                      {r.total_return_pct >= 0 ? "+" : ""}{r.total_return_pct.toFixed(1)}%
                    </td>
                    <td className={`py-2.5 pr-3 text-right font-bold ${r.win_rate >= 0.6 ? "text-green-400" : r.win_rate >= 0.5 ? "text-yellow-400" : "text-red-400"}`}>
                      {(r.win_rate * 100).toFixed(0)}%
                    </td>
                    <td className="py-2.5 pr-3 text-right text-text-secondary">{r.sharpe_ratio?.toFixed(1) ?? "—"}</td>
                    <td className="py-2.5 pr-3 text-right text-red-400">{r.max_drawdown_pct.toFixed(1)}%</td>
                    <td className="py-2.5 pr-3 text-right text-text-secondary">{r.closed_signals}</td>
                    <td className="py-2.5 text-right text-xs text-text-muted">{r.created_at ? new Date(r.created_at).toLocaleDateString() : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function MC({ label, value, color = "text-text-primary" }: { label: string; value: string; color?: string }) {
  return <div className="rounded-xl border border-border bg-surface-card p-4"><p className="text-xs text-text-muted">{label}</p><p className={`mt-1 text-2xl font-bold ${color}`}>{value}</p></div>;
}
function D({ label, value }: { label: string; value: string }) {
  return <div><span className="text-text-muted">{label}: </span><span className="font-medium text-text-primary">{value}</span></div>;
}
