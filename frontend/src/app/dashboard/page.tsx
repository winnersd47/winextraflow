"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useWebSocket } from "@/lib/ws";
import { SignalCard } from "@/components/signal-card";
import type { Signal, WSNewSignal } from "@/types";

const STATUS_FILTERS = [
  { value: "", label: "All" },
  { value: "active", label: "Active" },
  { value: "closed_tp", label: "TP Hit" },
  { value: "closed_sl", label: "SL Hit" },
  { value: "expired", label: "Expired" },
];

export default function DashboardPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [tickerFilter, setTickerFilter] = useState("");

  const fetchSignals = useCallback(async () => {
    try {
      const data = await api.getSignals({
        status: statusFilter || undefined,
        ticker: tickerFilter || undefined,
        limit: 50,
      });
      setSignals(data.items);
      setTotal(data.total);
    } catch (err) {
      console.error("Failed to fetch signals:", err);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, tickerFilter]);

  useEffect(() => {
    fetchSignals();
  }, [fetchSignals]);

  // Real-time: prepend new signals
  const handleNewSignal = useCallback((msg: WSNewSignal) => {
    // Refetch to get the full signal object
    fetchSignals();
  }, [fetchSignals]);

  const { connected } = useWebSocket(handleNewSignal);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Signal Feed</h1>
          <p className="text-sm text-gray-400">
            {total} signals{" "}
            <span
              className={`ml-2 inline-block h-2 w-2 rounded-full ${
                connected ? "bg-green-500" : "bg-red-500"
              }`}
            />
            <span className="ml-1 text-xs">
              {connected ? "Live" : "Reconnecting..."}
            </span>
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap gap-3">
        <input
          type="text"
          placeholder="Filter by ticker..."
          value={tickerFilter}
          onChange={(e) => setTickerFilter(e.target.value)}
          className="rounded-lg border border-gray-700 bg-surface px-3 py-2 text-sm text-white outline-none focus:border-brand-500"
        />
        <div className="flex gap-1">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setStatusFilter(f.value)}
              className={`rounded-lg px-3 py-2 text-sm transition ${
                statusFilter === f.value
                  ? "bg-brand-500/20 text-brand-500"
                  : "text-gray-400 hover:bg-surface-hover hover:text-white"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Signal list */}
      {loading ? (
        <div className="flex justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
        </div>
      ) : signals.length === 0 ? (
        <div className="rounded-xl border border-gray-800 bg-surface-card p-12 text-center">
          <p className="text-gray-400">No signals found</p>
          <p className="mt-1 text-sm text-gray-500">
            Signals will appear here when received from TradingView or Telegram
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {signals.map((signal) => (
            <SignalCard key={signal.id} signal={signal} />
          ))}
        </div>
      )}
    </div>
  );
}
