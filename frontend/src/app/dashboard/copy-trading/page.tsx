"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { timeAgo } from "@/lib/utils";
import type { CopyTradingStatus, CopyTradeResponse } from "@/types";

export default function CopyTradingPage() {
  const [status, setStatus] = useState<CopyTradingStatus | null>(null);
  const [trades, setTrades] = useState<CopyTradeResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [s, h] = await Promise.all([
          api.getCopyTradingStatus(),
          api.getCopyTradeHistory(),
        ]);
        setStatus(s);
        setTrades(h.items);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-2 text-2xl font-bold text-white">Copy Trading</h1>
      <p className="mb-6 text-sm text-gray-400">
        Automatically copy signals from strategies you subscribe to
      </p>

      {/* Status */}
      {status && (
        <>
          <div className="mb-6 rounded-xl border border-gray-800 bg-surface-card p-4">
            <div className="flex items-center gap-3">
              <span
                className={`h-3 w-3 rounded-full ${
                  status.enabled ? "bg-green-500" : "bg-gray-500"
                }`}
              />
              <span className="font-medium text-white">
                {status.enabled
                  ? "Copy Trading Active"
                  : "Copy Trading Inactive"}
              </span>
            </div>
            {!status.enabled && (
              <p className="mt-2 text-sm text-gray-400">
                To enable: subscribe to a strategy with auto-execute ON, and have
                an exchange account with auto-execute enabled.
              </p>
            )}
          </div>

          <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatCard label="Auto Subscriptions" value={String(status.active_subscriptions)} />
            <StatCard label="Auto Accounts" value={String(status.auto_execute_accounts)} />
            <StatCard label="Successful" value={String(status.successful_trades)} color="text-green-400" />
            <StatCard label="Failed" value={String(status.failed_trades)} color="text-red-400" />
          </div>
        </>
      )}

      {/* How it works */}
      <div className="mb-6 rounded-xl border border-gray-800 bg-surface-card p-4">
        <h3 className="mb-2 font-semibold text-white">How Copy Trading Works</h3>
        <ol className="space-y-1 text-sm text-gray-400">
          <li>1. Subscribe to a strategy in the <span className="text-brand-500">Marketplace</span></li>
          <li>2. Enable <span className="text-white">auto-execute</span> on the subscription</li>
          <li>3. Add an exchange account in <span className="text-brand-500">Execution</span> with auto-execute ON</li>
          <li>4. New signals are automatically traded on your account</li>
        </ol>
      </div>

      {/* Trade History */}
      <div className="rounded-xl border border-gray-800 bg-surface-card p-6">
        <h2 className="mb-4 text-lg font-bold text-white">
          Copy Trade History ({trades.length})
        </h2>
        {trades.length === 0 ? (
          <p className="text-center text-gray-400 py-8">
            No copied trades yet
          </p>
        ) : (
          <div className="space-y-2">
            {trades.map((trade) => (
              <div
                key={trade.id}
                className="flex items-center justify-between rounded-lg bg-surface p-3"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`rounded px-2 py-0.5 text-xs font-bold ${
                      trade.status === "executed"
                        ? "bg-green-500/20 text-green-400"
                        : trade.status === "failed"
                          ? "bg-red-500/20 text-red-400"
                          : trade.status === "skipped"
                            ? "bg-yellow-500/20 text-yellow-400"
                            : "bg-gray-500/20 text-gray-400"
                    }`}
                  >
                    {trade.status}
                  </span>
                  <span className="text-sm text-gray-300">
                    Signal: {trade.signal_id.slice(0, 8)}...
                  </span>
                </div>
                <div className="text-right">
                  {trade.error_message && (
                    <p className="text-xs text-red-400">{trade.error_message}</p>
                  )}
                  <p className="text-xs text-gray-500">{timeAgo(trade.created_at)}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, color = "text-white" }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-xl border border-gray-800 bg-surface-card p-4">
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${color}`}>{value}</p>
    </div>
  );
}
