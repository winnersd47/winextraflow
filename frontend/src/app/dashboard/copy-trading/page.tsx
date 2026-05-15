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
  const { t } = useI18n();

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
            {trades.map((trade) => (
              <div key={trade.id} className="flex items-center justify-between rounded-lg bg-surface p-3">
                <div className="flex items-center gap-3">
                  <span className={`rounded px-2 py-0.5 text-xs font-bold ${trade.status === "executed" ? "bg-green-500/20 text-green-400" : trade.status === "failed" ? "bg-red-500/20 text-red-400" : trade.status === "skipped" ? "bg-yellow-500/20 text-yellow-400" : "bg-gray-500/20 text-text-secondary"}`}>{trade.status}</span>
                  <span className="text-sm text-text-secondary">Signal: {trade.signal_id.slice(0, 8)}...</span>
                </div>
                <div className="text-right">
                  {trade.error_message && <p className="text-xs text-red-400">{trade.error_message}</p>}
                  <p className="text-xs text-text-muted">{timeAgo(trade.created_at)}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function SC({ label, value, color = "text-text-primary" }: { label: string; value: string; color?: string }) {
  return <div className="rounded-xl border border-border bg-surface-card p-4"><p className="text-xs text-text-muted">{label}</p><p className={`mt-1 text-2xl font-bold ${color}`}>{value}</p></div>;
}
