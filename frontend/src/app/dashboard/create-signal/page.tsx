"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import type { Provider } from "@/types";

export default function CreateSignalPage() {
  const { t, locale } = useI18n();
  const { user } = useAuth();
  const router = useRouter();
  const isRu = locale === "ru";
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [providerId, setProviderId] = useState("");
  const [ticker, setTicker] = useState("");
  const [action, setAction] = useState("buy");
  const [entryPrice, setEntryPrice] = useState("");
  const [takeProfit, setTakeProfit] = useState("");
  const [stopLoss, setStopLoss] = useState("");
  const [timeframe, setTimeframe] = useState("");

  const canCreate = user?.role === "analyst" || user?.role === "admin";

  useEffect(() => {
    async function load() {
      try {
        const data = await api.getProviders();
        setProviders(data.items);
        if (data.items.length > 0) setProviderId(data.items[0].id);
      } catch {}
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
    } catch { setError(isRu ? "Ошибка сети" : "Network error"); }
    finally { setSubmitting(false); }
  };

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;

  // Access denied for non-analysts
  if (!canCreate) {
    return (
      <div className="mx-auto max-w-2xl py-12">
        <div className="rounded-2xl border border-border bg-surface-card p-8 text-center">
          <h1 className="mb-4 text-2xl font-bold text-text-primary">
            {isRu ? "Создание сигналов" : "Signal Creation"}
          </h1>
          <p className="mb-4 text-text-secondary">
            {isRu
              ? "Создание торговых сигналов доступно только сотрудникам с ролью Аналитик. Аналитик — это специалист, который анализирует рынок и публикует сигналы для подписчиков платформы."
              : "Creating trading signals is only available to employees with the Analyst role. An Analyst is a specialist who analyzes the market and publishes signals for platform subscribers."}
          </p>
          <div className="mb-6 rounded-lg bg-surface p-4 text-left">
            <p className="mb-2 text-sm font-bold text-text-primary">{isRu ? "Кто может создавать сигналы:" : "Who can create signals:"}</p>
            <ul className="space-y-2 text-sm text-text-secondary">
              <li className="flex items-center gap-2">
                <span className="rounded bg-blue-500/20 px-2 py-0.5 text-xs font-bold text-blue-400">Analyst</span>
                {isRu ? "Аналитик — сотрудник, публикует сигналы от имени провайдера" : "Analyst — employee, publishes signals on behalf of a provider"}
              </li>
              <li className="flex items-center gap-2">
                <span className="rounded bg-brand-500/20 px-2 py-0.5 text-xs font-bold text-brand-500">Admin</span>
                {isRu ? "Администратор — полный доступ ко всем функциям" : "Admin — full access to all features"}
              </li>
            </ul>
          </div>
          <p className="text-xs text-text-muted">
            {isRu
              ? "Ваша текущая роль: " + (user?.role || "user") + ". Обратитесь к администратору для назначения роли Аналитик."
              : "Your current role: " + (user?.role || "user") + ". Contact the administrator to be assigned the Analyst role."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-2 text-2xl font-bold text-text-primary">{t("createSignal.title")}</h1>
      <p className="mb-4 text-sm text-text-secondary">{t("createSignal.subtitle")}</p>

      {/* Role badge + explanation */}
      <div className="mb-6 rounded-lg border border-border bg-surface-card p-4">
        <div className="flex items-center gap-3">
          <span className={`rounded px-2 py-0.5 text-xs font-bold ${user?.role === "admin" ? "bg-brand-500/20 text-brand-500" : "bg-blue-500/20 text-blue-400"}`}>
            {user?.role === "admin" ? "Admin" : "Analyst"}
          </span>
          <p className="text-sm text-text-secondary">
            {isRu
              ? "Вы публикуете сигнал от имени провайдера. Провайдер — это источник сигналов (канал, алгоритм, аналитик). Выберите провайдера, к которому относится ваш сигнал."
              : "You publish a signal on behalf of a provider. A provider is a signal source (channel, algorithm, analyst). Select the provider your signal belongs to."}
          </p>
        </div>
      </div>

      {providers.length === 0 && (
        <div className="mb-6 rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-4 text-sm text-yellow-400">
          {t("createSignal.noProviders")}
        </div>
      )}

      {error && <div className="mb-4 rounded-lg bg-red-500/10 p-3 text-sm text-red-400">{error}</div>}
      {success && <div className="mb-4 rounded-lg bg-green-500/10 p-3 text-sm text-green-400">{success}</div>}

      <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-border bg-surface-card p-6">
        <div>
          <label className="mb-1 block text-sm text-text-secondary">
            {isRu ? "Провайдер (источник сигнала)" : "Provider (signal source)"}
          </label>
          <select value={providerId} onChange={(e) => setProviderId(e.target.value)} required className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-text-primary">
            {providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <p className="mt-1 text-xs text-text-muted">
            {isRu ? "К какому источнику относится этот сигнал. Статистика провайдера обновится автоматически." : "Which source this signal belongs to. Provider stats will update automatically."}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1 block text-sm text-text-secondary">{t("createSignal.ticker")}</label>
            <input type="text" value={ticker} onChange={(e) => setTicker(e.target.value)} required placeholder="BTCUSDT" className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-text-primary outline-none focus:border-brand-500" />
          </div>
          <div>
            <label className="mb-1 block text-sm text-text-secondary">{t("createSignal.action")}</label>
            <select value={action} onChange={(e) => setAction(e.target.value)} className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-text-primary">
              <option value="buy">{isRu ? "BUY (Покупка)" : "BUY"}</option>
              <option value="sell">{isRu ? "SELL (Продажа)" : "SELL"}</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="mb-1 block text-sm text-text-secondary">{isRu ? "Цена входа" : "Entry Price"}</label>
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
