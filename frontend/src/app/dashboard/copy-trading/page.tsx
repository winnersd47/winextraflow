"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { timeAgo } from "@/lib/utils";
import type { CopyTradingStatus, CopyTradeResponse } from "@/types";

const PAGE_SIZE = 10;

export default function CopyTradingPage() {
  const [status, setStatus] = useState<CopyTradingStatus | null>(null);
  const [trades, setTrades] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingPage, setLoadingPage] = useState(false);
  const { t, locale } = useI18n();
  const isRu = locale === "ru";

  const loadPage = async (p: number) => {
    setLoadingPage(true);
    try {
      const token = localStorage.getItem("token");
      const h = await fetch(`/api/v1/copy-trading/history?skip=${p * PAGE_SIZE}&limit=${PAGE_SIZE}`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then(r => r.json());
      setTrades(h.items);
      setTotal(h.total);
      setPage(p);
    } catch {}
    finally { setLoadingPage(false); }
  };

  useEffect(() => {
    async function load() {
      try {
        const [s] = await Promise.all([api.getCopyTradingStatus()]);
        setStatus(s);
        await loadPage(0);
      } catch {}
      finally { setLoading(false); }
    }
    load();
  }, []);

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-2 text-2xl font-bold text-text-primary">{t("copyTrading.title")}</h1>
      <p className="mb-6 text-sm text-text-secondary">{t("copyTrading.subtitle")}</p>

      {status && (
        <>
          <div className="mb-6 rounded-xl border border-border bg-surface-card p-4">
            <div className="flex items-center gap-3">
              <span className={`h-3 w-3 rounded-full ${status.enabled ? "bg-green-500" : "bg-gray-500"}`} />
              <span className="font-medium text-text-primary">{status.enabled ? t("copyTrading.active") : t("copyTrading.inactive")}</span>
            </div>
            {!status.enabled && <p className="mt-2 text-sm text-text-secondary">{t("copyTrading.howToEnable")}</p>}
          </div>
          <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <SC label={t("copyTrading.autoSubs")} value={String(status.active_subscriptions)} />
            <SC label={t("copyTrading.autoAccounts")} value={String(status.auto_execute_accounts)} />
            <SC label={t("copyTrading.successful")} value={String(status.successful_trades)} color="text-green-400" />
            <SC label={t("copyTrading.failed")} value={String(status.failed_trades)} color="text-red-400" />
          </div>
        </>
      )}

      <div className="mb-6 rounded-xl border border-border bg-surface-card p-4">
        <h3 className="mb-2 font-semibold text-text-primary">{t("copyTrading.howTitle")}</h3>
        <ol className="space-y-1 text-sm text-text-secondary">
          <li>{t("copyTrading.step1")}</li>
          <li>{t("copyTrading.step2")}</li>
          <li>{t("copyTrading.step3")}</li>
          <li>{t("copyTrading.step4")}</li>
        </ol>
      </div>

      <div className="rounded-xl border border-border bg-surface-card p-6">
        <h2 className="mb-4 text-lg font-bold text-text-primary">{t("copyTrading.history")} ({total})</h2>
        {trades.length === 0 ? (
          <p className="py-8 text-center text-text-secondary">{t("copyTrading.noTrades")}</p>
        ) : (
          <>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-text-muted">
                <tr>
                  <th className="pb-2 pr-3">{isRu ? "Статус" : "Status"}</th>
                  <th className="pb-2 pr-3">{isRu ? "Тикер" : "Ticker"}</th>
                  <th className="pb-2 pr-3">{isRu ? "Действие" : "Action"}</th>
                  <th className="pb-2 pr-3 text-right">{isRu ? "Цена входа" : "Entry Price"}</th>
                  <th className="pb-2 pr-3 text-right">{isRu ? "Прибыль" : "Profit"}</th>
                  <th className="pb-2 pr-3">{isRu ? "Качество" : "Quality"}</th>
                  <th className="pb-2 pr-3">{isRu ? "Стратегия" : "Strategy"}</th>
                  <th className="pb-2 text-right">{isRu ? "Когда" : "Time"}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {trades.map((trade: any) => {
                  const statusRu: Record<string, string> = { executed: "Исполнено", failed: "Ошибка", skipped: "Пропущено", pending: "Ожидание" };
                  const statusEn: Record<string, string> = { executed: "Executed", failed: "Failed", skipped: "Skipped", pending: "Pending" };
                  const errorRu: Record<string, string> = { "Insufficient balance": "Недостаточно средств", "Exchange connection error": "Ошибка соединения", "Exchange order execution failed": "Ошибка ордера" };
                  const statusLabel = isRu ? (statusRu[trade.status] || trade.status) : (statusEn[trade.status] || trade.status);
                  const errorLabel = trade.error_message ? (isRu ? (errorRu[trade.error_message] || trade.error_message) : trade.error_message) : null;
                  const profitPct = trade.profit_pct;
                  const hasTicker = !!trade.ticker;

                  return (
                    <tr key={trade.id}>
                      {/* Статус */}
                      <td className="py-2.5 pr-3">
                        <span className={`rounded px-2 py-0.5 text-xs font-bold ${trade.status === "executed" ? "bg-green-500/20 text-green-400" : trade.status === "failed" ? "bg-red-500/20 text-red-400" : "bg-yellow-500/20 text-yellow-400"}`}>
                          {statusLabel}
                        </span>
                        {errorLabel && <p className="mt-0.5 text-xs text-red-400">{errorLabel}</p>}
                      </td>
                      {/* Тикер */}
                      <td className="py-2.5 pr-3 font-bold text-text-primary">
                        {hasTicker ? trade.ticker : <span className="text-text-muted font-normal">{trade.signal_id.slice(0, 8)}...</span>}
                      </td>
                      {/* Действие */}
                      <td className="py-2.5 pr-3">
                        {hasTicker && (
                          <span className={`text-xs font-bold uppercase ${trade.action === "buy" ? "text-green-400" : "text-red-400"}`}>
                            {trade.action === "buy" ? (isRu ? "Покупка" : "Buy") : (isRu ? "Продажа" : "Sell")}
                          </span>
                        )}
                      </td>
                      {/* Цена входа */}
                      <td className="py-2.5 pr-3 text-right text-text-secondary">
                        {trade.entry_price != null ? trade.entry_price.toLocaleString(isRu ? "ru-RU" : "en-US", { maximumFractionDigits: 6 }) : "—"}
                      </td>
                      {/* Прибыль */}
                      <td className="py-2.5 pr-3 text-right">
                        {profitPct != null ? (
                          <span className={`font-bold ${profitPct >= 0 ? "text-green-400" : "text-red-400"}`}>
                            {profitPct >= 0 ? "+" : ""}{profitPct.toFixed(2)}%
                          </span>
                        ) : (
                          <span className="text-text-muted">{trade.status === "executed" ? (isRu ? "Открыта" : "Open") : "—"}</span>
                        )}
                      </td>
                      {/* Качество */}
                      <td className="py-2.5 pr-3">
                        {trade.ai_confidence != null ? (
                          <span className={`text-xs font-bold ${trade.ai_confidence >= 0.7 ? "text-green-400" : trade.ai_confidence >= 0.4 ? "text-yellow-400" : "text-red-400"}`}>
                            {(trade.ai_confidence * 100).toFixed(0)}%
                          </span>
                        ) : "—"}
                      </td>
                      {/* Стратегия */}
                      <td className="py-2.5 pr-3">
                        {trade.strategy_name ? (
                          <span className="rounded bg-purple-500/10 px-2 py-0.5 text-xs text-purple-400">{trade.strategy_name.replace("[TEST] ", "")}</span>
                        ) : "—"}
                      </td>
                      {/* Когда */}
                      <td className="py-2.5 text-right text-xs text-text-muted">
                        {timeAgo(trade.created_at)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {loadingPage && (
              <div className="flex justify-center py-4"><div className="h-5 w-5 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>
            )}
          </div>

          {/* Pagination */}
          {total > PAGE_SIZE && (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-xs text-text-muted">
                {isRu
                  ? `${page * PAGE_SIZE + 1}–${Math.min((page + 1) * PAGE_SIZE, total)} из ${total}`
                  : `${page * PAGE_SIZE + 1}–${Math.min((page + 1) * PAGE_SIZE, total)} of ${total}`}
              </p>
              <div className="flex gap-1">
                {Array.from({ length: Math.ceil(total / PAGE_SIZE) }, (_, i) => (
                  <button
                    key={i}
                    onClick={() => loadPage(i)}
                    disabled={loadingPage}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                      i === page
                        ? "bg-brand-500 text-white"
                        : "bg-surface-hover text-text-secondary hover:text-text-primary"
                    }`}
                  >
                    {i + 1}
                  </button>
                ))}
              </div>
            </div>
          )}
          </>
        )}
      </div>
    </div>
  );
}

function SC({ label, value, color = "text-text-primary" }: { label: string; value: string; color?: string }) {
  return <div className="rounded-xl border border-border bg-surface-card p-4"><p className="text-xs text-text-muted">{label}</p><p className={`mt-1 text-2xl font-bold ${color}`}>{value}</p></div>;
}
