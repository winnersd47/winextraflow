"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Provider } from "@/types";

export default function CreateSignalPage() {
  const { t } = useI18n();
  const router = useRouter();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Form
  const [providerId, setProviderId] = useState("");
  const [ticker, setTicker] = useState("");
  const [action, setAction] = useState("buy");
  const [entryPrice, setEntryPrice] = useState("");
  const [takeProfit, setTakeProfit] = useState("");
  const [stopLoss, setStopLoss] = useState("");
  const [timeframe, setTimeframe] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const data = await api.getProviders();
        setProviders(data.items);
        if (data.items.length > 0) setProviderId(data.items[0].id);
      } catch (err) { console.error(err); }
      finally { setLoading(false); }
    }
    load();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSubmitting(true);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch("/api/v1/signals", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          provider_id: providerId,
          ticker: ticker.toUpperCase(),
          action,
          entry_price: parseFloat(entryPrice),
          take_profit: takeProfit ? parseFloat(takeProfit) : null,
          stop_loss: stopLoss ? parseFloat(stopLoss) : null,
          timeframe: timeframe || null,
        }),
      });
      if (res.ok) {
        setSuccess(t("createSignal.success"));
        setTicker("");
        setEntryPrice("");
        setTakeProfit("");
        setStopLoss("");
      } else {
        const d = await res.json();
        setError(d.detail || "Failed");
      }
    } catch { setError("Network error"); }
    finally { setSubmitting(false); }
  };

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-2 text-2xl font-bold text-text-primary">{t("createSignal.title")}</h1>
      <p className="mb-6 text-sm text-text-secondary">{t("createSignal.subtitle")}</p>

      {providers.length === 0 && (
        <div className="mb-6 rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-4 text-sm text-yellow-400">
          {t("createSignal.noProviders")}
        </div>
      )}

      {error && <div className="mb-4 rounded-lg bg-red-500/10 p-3 text-sm text-red-400">{error}</div>}
      {success && <div className="mb-4 rounded-lg bg-green-500/10 p-3 text-sm text-green-400">{success}</div>}

      <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-border bg-surface-card p-6">
        <div>
          <label className="mb-1 block text-sm text-text-secondary">{t("createSignal.provider")}</label>
          <select value={providerId} onChange={(e) => setProviderId(e.target.value)} required className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-text-primary">
            {providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1 block text-sm text-text-secondary">{t("createSignal.ticker")}</label>
            <input type="text" value={ticker} onChange={(e) => setTicker(e.target.value)} required placeholder="BTCUSDT" className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-text-primary outline-none focus:border-brand-500" />
          </div>
          <div>
            <label className="mb-1 block text-sm text-text-secondary">{t("createSignal.action")}</label>
            <select value={action} onChange={(e) => setAction(e.target.value)} className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-text-primary">
              <option value="buy">BUY</option>
              <option value="sell">SELL</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="mb-1 block text-sm text-text-secondary">{t("signals.entry")}</label>
            <input type="number" step="any" value={entryPrice} onChange={(e) => setEntryPrice(e.target.value)} required placeholder="65000" className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-text-primary outline-none focus:border-brand-500" />
          </div>
          <div>
            <label className="mb-1 block text-sm text-text-secondary">Take Profit</label>
            <input type="number" step="any" value={takeProfit} onChange={(e) => setTakeProfit(e.target.value)} placeholder="70000" className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-text-primary outline-none focus:border-brand-500" />
          </div>
          <div>
            <label className="mb-1 block text-sm text-text-secondary">Stop Loss</label>
            <input type="number" step="any" value={stopLoss} onChange={(e) => setStopLoss(e.target.value)} placeholder="62000" className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-text-primary outline-none focus:border-brand-500" />
          </div>
        </div>

        <div>
          <label className="mb-1 block text-sm text-text-secondary">{t("createSignal.timeframe")}</label>
          <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-text-primary">
            <option value="">—</option>
            <option value="1m">1m</option>
            <option value="5m">5m</option>
            <option value="15m">15m</option>
            <option value="1h">1h</option>
            <option value="4h">4h</option>
            <option value="1d">1D</option>
            <option value="1w">1W</option>
          </select>
        </div>

        <button type="submit" disabled={submitting || !providerId} className="w-full rounded-lg bg-brand-600 py-3 font-medium text-white hover:bg-brand-700 disabled:opacity-50">
          {submitting ? "..." : t("createSignal.submit")}
        </button>
      </form>
    </div>
  );
}
