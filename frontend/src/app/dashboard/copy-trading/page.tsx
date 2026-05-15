"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { timeAgo } from "@/lib/utils";
import type { CopyTradingStatus, CopyTradeResponse } from "@/types";

export default function CopyTradingPage() {
  const [status, setStatus] = useState<CopyTradingStatus | null>(null);
  const [trades, setTrades] = useState<CopyTradeResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const { t, locale } = useI18n();
  const isRu = locale === "ru";

  useEffect(() => {
    async function load() {
      try {
        const [s, h] = await Promise.all([api.getCopyTradingStatus(), api.getCopyTradeHistory()]);
        setStatus(s);
        setTrades(h.items);
      } catch (err) { console.error(err); }
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
        <h2 className="mb-4 text-lg font-bold text-text-primary">{t("copyTrading.history")} ({trades.length})</h2>
        {trades.length === 0 ? (
          <p className="py-8 text-center text-text-secondary">{t("copyTrading.noTrades")}</p>
        ) : (
          <div className="space-y-2">
            {trades.map((trade: any) => {
              const statusRu: Record<string, string> = { executed: "Исполнено", failed: "Ошибка", skipped: "Пропущено", pending: "Ожидание" };
              const statusEn: Record<string, string> = { executed: "Executed", failed: "Failed", skipped: "Skipped", pending: "Pending" };
              const errorRu: Record<string, string> = { "Insufficient balance": "Недостаточно средств", "Exchange connection error": "Ошибка подключения к бирже", "Exchange order execution failed": "Ошибка исполнения ордера" };
              const statusLabel = isRu ? (statusRu[trade.status] || trade.status) : (statusEn[trade.status] || trade.status);
              const errorLabel = trade.error_message ? (isRu ? (errorRu[trade.error_message] || trade.error_message) : trade.error_message) : null;

              return (
                <div key={trade.id} className="flex items-center justify-between rounded-lg bg-surface p-3">
                  <div className="flex items-center gap-3">
                    <span className={`rounded px-2 py-0.5 text-xs font-bold ${trade.status === "executed" ? "bg-green-500/20 text-green-400" : trade.status === "failed" ? "bg-red-500/20 text-red-400" : trade.status === "skipped" ? "bg-yellow-500/20 text-yellow-400" : "bg-surface-hover text-text-secondary"}`}>
                      {statusLabel}
                    </span>
                    {trade.ticker ? (
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-text-primary">{trade.ticker}</span>
                        <span className={`text-xs font-bold uppercase ${trade.action === "buy" ? "text-green-400" : "text-red-400"}`}>
                          {trade.action === "buy" ? (isRu ? "ПОКУПКА" : "BUY") : (isRu ? "ПРОДАЖА" : "SELL")}
                        </span>
                        {trade.entry_price && (
                          <span className="text-xs text-text-muted">@ {trade.entry_price.toLocaleString()}</span>
                        )}
                      </div>
                    ) : (
                      <span className="text-sm text-text-muted">ID: {trade.signal_id.slice(0, 8)}...</span>
                    )}
                    {trade.strategy_name && (
                      <span className="rounded bg-purple-500/10 px-2 py-0.5 text-xs text-purple-400">{trade.strategy_name}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-4">
                    {trade.ai_confidence != null && (
                      <span className={`text-xs font-bold ${trade.ai_confidence >= 0.7 ? "text-green-400" : trade.ai_confidence >= 0.4 ? "text-yellow-400" : "text-red-400"}`}>
                        {(trade.ai_confidence * 100).toFixed(0)}%
                      </span>
                    )}
                    <div className="text-right">
                      {errorLabel && <p className="text-xs text-red-400">{errorLabel}</p>}
                      <p className="text-xs text-text-muted">{timeAgo(trade.created_at)}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function SC({ label, value, color = "text-text-primary" }: { label: string; value: string; color?: string }) {
  return <div className="rounded-xl border border-border bg-surface-card p-4"><p className="text-xs text-text-muted">{label}</p><p className={`mt-1 text-2xl font-bold ${color}`}>{value}</p></div>;
}
