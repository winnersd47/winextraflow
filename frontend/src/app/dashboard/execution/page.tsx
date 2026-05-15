"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatPrice, timeAgo } from "@/lib/utils";
import type { ExchangeAccountResponse, OrderResponse } from "@/types";

export default function ExecutionPage() {
  const [accounts, setAccounts] = useState<ExchangeAccountResponse[]>([]);
  const [orders, setOrders] = useState<OrderResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [formExchange, setFormExchange] = useState("demo");
  const [formLabel, setFormLabel] = useState("");
  const [formKey, setFormKey] = useState("");
  const [formSecret, setFormSecret] = useState("");
  const [formAuto, setFormAuto] = useState(false);
  const [formError, setFormError] = useState("");
  const { t, locale } = useI18n();
  const isRu = locale === "ru";

  const load = async () => {
    try {
      const [accs, ords] = await Promise.all([api.getExchangeAccounts(), api.getOrders()]);
      setAccounts(accs);
      setOrders(ords.items);
    } catch {}
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleAddAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    try {
      await api.createExchangeAccount({ exchange: formExchange, label: formLabel || `${formExchange} account`, api_key: formKey || "demo", api_secret: formSecret || "demo", auto_execute: formAuto });
      setShowForm(false);
      setFormLabel("");
      setFormKey("");
      setFormSecret("");
      load();
    } catch (err: any) { setFormError(err.message); }
  };

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;

  // Split orders: active (pending/partial) vs completed (filled/failed)
  const activeOrders = orders.filter(o => o.status === "pending" || o.status === "partial");
  const completedCount = orders.length - activeOrders.length;

  const statusRu: Record<string, string> = { pending: "Ожидание", partial: "Частично", filled: "Исполнен", failed: "Ошибка", cancelled: "Отменён" };

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">{t("execution.title")}</h1>
          <p className="text-sm text-text-secondary">{t("execution.subtitle")}</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
          {showForm ? t("execution.cancel") : t("execution.addAccount")}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleAddAccount} className="mb-6 space-y-3 rounded-xl border border-border bg-surface-card p-6">
          {formError && <div className="rounded-lg bg-red-500/10 p-3 text-sm text-red-400">{formError}</div>}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs text-text-secondary">{t("execution.exchange")}</label>
              <select value={formExchange} onChange={(e) => setFormExchange(e.target.value)} className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary">
                <optgroup label={t("execution.groupPaper")}>
                  <option value="demo">Demo (Paper Trading)</option>
                </optgroup>
                <optgroup label={t("execution.groupCrypto")}>
                  <option value="binance">Binance</option>
                  <option value="bybit">Bybit</option>
                  <option value="okx">OKX</option>
                  <option value="kraken">Kraken</option>
                </optgroup>
                <optgroup label={t("execution.groupForex")}>
                  <option value="metatrader5">MetaTrader 5</option>
                  <option value="interactive_brokers">Interactive Brokers</option>
                </optgroup>
                <optgroup label={t("execution.groupStocks")}>
                  <option value="tinkoff">Tinkoff Invest</option>
                  <option value="exante">Exante</option>
                </optgroup>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-secondary">{t("execution.label")}</label>
              <input type="text" value={formLabel} onChange={(e) => setFormLabel(e.target.value)} placeholder="My Account" className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-500" />
            </div>
          </div>
          {formExchange !== "demo" && (
            <div className="grid grid-cols-2 gap-3">
              <div><label className="mb-1 block text-xs text-text-secondary">{t("execution.apiKey")}</label><input type="password" value={formKey} onChange={(e) => setFormKey(e.target.value)} className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-500" /></div>
              <div><label className="mb-1 block text-xs text-text-secondary">{t("execution.apiSecret")}</label><input type="password" value={formSecret} onChange={(e) => setFormSecret(e.target.value)} className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-500" /></div>
            </div>
          )}
          <label className="flex items-center gap-2 text-sm text-text-secondary">
            <input type="checkbox" checked={formAuto} onChange={(e) => setFormAuto(e.target.checked)} className="rounded" />
            {t("execution.autoExecute")}
          </label>
          <button type="submit" className="rounded-lg bg-brand-600 px-6 py-2 text-sm font-medium text-white hover:bg-brand-700">{t("execution.add")}</button>
        </form>
      )}

      {/* Exchange Accounts */}
      <div className="mb-8">
        <h2 className="mb-3 text-lg font-bold text-text-primary">{t("execution.accounts")} ({accounts.length})</h2>
        {accounts.length === 0 ? (
          <div className="rounded-xl border border-border bg-surface-card p-8 text-center text-text-secondary">{t("execution.noAccounts")}</div>
        ) : (
          <div className="space-y-2">
            {accounts.map((acc) => (
              <div key={acc.id} className="flex items-center justify-between rounded-xl border border-border bg-surface-card p-4">
                <div className="flex items-center gap-3">
                  <span className={`rounded px-2 py-0.5 text-xs font-bold uppercase ${
                    acc.exchange === "demo" ? "bg-purple-500/20 text-purple-400" :
                    ["binance","bybit","okx","kraken"].includes(acc.exchange) ? "bg-yellow-500/20 text-yellow-400" :
                    ["metatrader5","interactive_brokers"].includes(acc.exchange) ? "bg-blue-500/20 text-blue-400" :
                    "bg-green-500/20 text-green-400"
                  }`}>{acc.exchange === "interactive_brokers" ? "IBKR" : acc.exchange === "metatrader5" ? "MT5" : acc.exchange}</span>
                  <span className="font-medium text-text-primary">{acc.label}</span>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <span className={acc.auto_execute ? "text-green-400" : "text-text-muted"}>{acc.auto_execute ? t("execution.autoOn") : t("execution.manual")}</span>
                  <span className="text-text-muted">{isRu ? "Мин" : "Min"}: {(acc.min_confidence * 100).toFixed(0)}%</span>
                  <span className="text-text-muted">{isRu ? "Размер" : "Size"}: {acc.max_position_pct}%</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Active Orders Only */}
      <div>
        <h2 className="mb-3 text-lg font-bold text-text-primary">
          {isRu ? "Активные ордера" : "Active Orders"} ({activeOrders.length})
        </h2>
        {activeOrders.length === 0 ? (
          <div className="rounded-xl border border-border bg-surface-card p-8 text-center">
            <p className="text-text-secondary">{isRu ? "Нет активных ордеров" : "No active orders"}</p>
            <p className="mt-1 text-sm text-text-muted">
              {isRu ? "Ордера в ожидании и частично исполненные отображаются здесь." : "Pending and partially filled orders appear here."}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-border">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-surface-card text-text-muted">
                <tr>
                  <th className="p-3">{t("execution.symbol")}</th>
                  <th className="p-3">{t("execution.side")}</th>
                  <th className="p-3">{t("execution.qty")}</th>
                  <th className="p-3">{t("execution.price")}</th>
                  <th className="p-3">{t("signals.status")}</th>
                  <th className="p-3">{t("execution.exchange")}</th>
                  <th className="p-3">{t("execution.time")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {activeOrders.map((o) => (
                  <tr key={o.id} className="bg-surface-card text-text-secondary">
                    <td className="p-3 font-medium text-text-primary">{o.symbol}</td>
                    <td className={`p-3 font-bold uppercase ${o.side === "buy" ? "text-green-400" : "text-red-400"}`}>
                      {o.side === "buy" ? (isRu ? "Покупка" : "Buy") : (isRu ? "Продажа" : "Sell")}
                    </td>
                    <td className="p-3">{o.quantity}</td>
                    <td className="p-3">{o.filled_price ? formatPrice(o.filled_price) : "—"}</td>
                    <td className="p-3">
                      <span className="rounded bg-yellow-500/20 px-2 py-0.5 text-xs text-yellow-400">
                        {isRu ? (statusRu[o.status] || o.status) : o.status}
                      </span>
                    </td>
                    <td className="p-3 text-text-muted">{o.exchange}</td>
                    <td className="p-3 text-text-muted">{timeAgo(o.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Link to copy trading for completed history */}
        {completedCount > 0 && (
          <div className="mt-4 rounded-lg border border-border bg-surface-card p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-text-secondary">
                {isRu
                  ? `${completedCount} завершённых ордеров (исполненные и с ошибками) доступны в истории копитрейдинга`
                  : `${completedCount} completed orders (filled and failed) available in copy trading history`}
              </p>
              <Link href="/dashboard/copy-trading" className="rounded-lg bg-brand-600/10 px-4 py-2 text-sm font-medium text-brand-500 hover:bg-brand-600/20">
                {isRu ? "Открыть историю" : "View History"}
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
