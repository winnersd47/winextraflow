"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useI18n } from "@/lib/i18n";
import { api } from "@/lib/api";
import { formatPrice, timeAgo } from "@/lib/utils";
import type { ExchangeAccountResponse, OrderResponse } from "@/types";

const JournalPage = dynamic(() => import("@/app/dashboard/journal/page"), { ssr: false });
const CopyTradingPage = dynamic(() => import("@/app/dashboard/copy-trading/page"), { ssr: false });

interface Position {
  id: string; ticker: string; action: string; entry_price: number;
  quantity: number; value: number; opened_at: string | null; note: string | null;
}
interface EquityPoint { date: string | null; pnl: number; ticker: string }
interface PortfolioData {
  open_positions: number; total_invested: number; total_realized_pnl: number;
  total_trades: number; win_rate: number; filled_orders: number; pending_orders: number;
  positions: Position[]; allocation: Record<string, number>; equity_curve: EquityPoint[];
}

type Tab = "overview" | "journal" | "accounts" | "orders" | "copy-trading";

const STATUS_RU: Record<string, string> = { pending: "Ожидание", partial: "Частично", filled: "Исполнен", failed: "Ошибка", cancelled: "Отменён" };
const STATUS_COLOR: Record<string, string> = { pending: "bg-yellow-500/20 text-yellow-400", partial: "bg-blue-500/20 text-blue-400", filled: "bg-green-500/20 text-green-400", failed: "bg-red-500/20 text-red-400", cancelled: "bg-gray-500/20 text-gray-400" };

export default function PortfolioPage() {
  const [data, setData] = useState<PortfolioData | null>(null);
  const [accounts, setAccounts] = useState<ExchangeAccountResponse[]>([]);
  const [orders, setOrders] = useState<OrderResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("overview");
  const [showForm, setShowForm] = useState(false);
  const [formExchange, setFormExchange] = useState("demo");
  const [formLabel, setFormLabel] = useState("");
  const [formKey, setFormKey] = useState("");
  const [formSecret, setFormSecret] = useState("");
  const [formAuto, setFormAuto] = useState(false);
  const [formError, setFormError] = useState("");
  const { t, locale } = useI18n();
  const isRu = locale === "ru";

  const loadAll = async () => {
    try {
      const token = localStorage.getItem("token");
      const safe = (p: Promise<Response>) => p.then(r => r.ok ? r.json() : null).catch(() => null);
      const [pf, accs, ords] = await Promise.all([
        safe(fetch("/api/v1/portfolio/summary", { headers: { Authorization: `Bearer ${token}` } })),
        api.getExchangeAccounts().catch(() => []),
        api.getOrders().catch(() => ({ items: [] })),
      ]);
      if (pf) setData(pf);
      setAccounts(accs || []);
      setOrders(ords?.items || []);
    } catch {}
    finally { setLoading(false); }
  };

  useEffect(() => { loadAll(); }, []);

  const handleAddAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    try {
      await api.createExchangeAccount({
        exchange: formExchange, label: formLabel || `${formExchange} account`,
        api_key: formKey || "demo", api_secret: formSecret || "demo", auto_execute: formAuto,
      });
      setShowForm(false); setFormLabel(""); setFormKey(""); setFormSecret("");
      loadAll();
    } catch (err: any) { setFormError(err.message); }
  };

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;

  const allocationEntries = data ? Object.entries(data.allocation).sort((a, b) => b[1] - a[1]) : [];
  const COLORS = ["bg-brand-500", "bg-blue-500", "bg-purple-500", "bg-yellow-500", "bg-red-500", "bg-cyan-500", "bg-pink-500"];
  const activeOrders = orders.filter(o => o.status === "pending" || o.status === "partial");
  const completedOrders = orders.filter(o => o.status !== "pending" && o.status !== "partial");

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">{isRu ? "Портфель и исполнение" : "Portfolio & Execution"}</h1>
          <p className="text-sm text-text-secondary">
            {accounts.length} {isRu ? "аккаунтов" : "accounts"} · {orders.length} {isRu ? "ордеров" : "orders"}
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="mb-4 flex gap-2">
        {([
          { key: "overview" as Tab, ru: "Обзор", en: "Overview" },
          { key: "journal" as Tab, ru: "Журнал", en: "Journal" },
          { key: "accounts" as Tab, ru: `Биржи (${accounts.length})`, en: `Exchanges (${accounts.length})` },
          { key: "orders" as Tab, ru: `Ордера (${orders.length})`, en: `Orders (${orders.length})` },
          { key: "copy-trading" as Tab, ru: "Копитрейдинг", en: "Copy Trading" },
        ]).map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition ${tab === t.key ? "bg-brand-500 text-white" : "text-text-secondary hover:bg-surface-hover"}`}>
            {isRu ? t.ru : t.en}
          </button>
        ))}
      </div>

      {/* ═══ OVERVIEW TAB ═══ */}
      {tab === "overview" && data && (
        <>
          {/* Summary cards */}
          <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-xl border border-border bg-surface-card p-4 text-center">
              <div className="text-xs text-text-muted">{isRu ? "Открытых позиций" : "Open Positions"}</div>
              <div className="text-2xl font-bold text-text-primary">{data.open_positions}</div>
            </div>
            <div className="rounded-xl border border-border bg-surface-card p-4 text-center">
              <div className="text-xs text-text-muted">{isRu ? "Инвестировано" : "Invested"}</div>
              <div className="text-2xl font-bold text-text-primary">{data.total_invested.toLocaleString()}</div>
            </div>
            <div className="rounded-xl border border-border bg-surface-card p-4 text-center">
              <div className="text-xs text-text-muted">{isRu ? "Реализованный P&L" : "Realized P&L"}</div>
              <div className={`text-2xl font-bold ${data.total_realized_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                {data.total_realized_pnl >= 0 ? "+" : ""}{data.total_realized_pnl.toLocaleString()}
              </div>
            </div>
            <div className="rounded-xl border border-border bg-surface-card p-4 text-center">
              <div className="text-xs text-text-muted">Win Rate</div>
              <div className={`text-2xl font-bold ${data.win_rate >= 0.5 ? "text-green-400" : "text-red-400"}`}>
                {(data.win_rate * 100).toFixed(0)}%
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {/* Allocation */}
            <div className="rounded-xl border border-border bg-surface-card p-4">
              <h3 className="mb-3 font-bold text-text-primary">{isRu ? "Распределение по активам" : "Asset Allocation"}</h3>
              {allocationEntries.length === 0 ? (
                <p className="text-sm text-text-muted">{isRu ? "Нет открытых позиций" : "No open positions"}</p>
              ) : (
                <div className="space-y-2">
                  {allocationEntries.map(([ticker, pct], i) => (
                    <div key={ticker}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="font-medium text-text-primary">{ticker}</span>
                        <span className="text-text-muted">{pct}%</span>
                      </div>
                      <div className="h-3 rounded-full bg-surface overflow-hidden">
                        <div className={`h-full rounded-full ${COLORS[i % COLORS.length]} transition-all`} style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Equity curve */}
            <div className="rounded-xl border border-border bg-surface-card p-4">
              <h3 className="mb-3 font-bold text-text-primary">{isRu ? "Кривая доходности" : "Equity Curve"}</h3>
              {data.equity_curve.length === 0 ? (
                <p className="text-sm text-text-muted">{isRu ? "Закройте сделки для построения кривой" : "Close trades to build the curve"}</p>
              ) : (
                <div className="space-y-1 max-h-64 overflow-y-auto">
                  {data.equity_curve.map((p, i) => {
                    const maxPnl = Math.max(...data.equity_curve.map(e => Math.abs(e.pnl)), 1);
                    const width = Math.abs(p.pnl) / maxPnl * 100;
                    return (
                      <div key={i} className="flex items-center gap-2 text-xs">
                        <span className="w-16 text-text-muted shrink-0">
                          {p.date ? new Date(p.date).toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" }) : "—"}
                        </span>
                        <span className="w-12 text-text-muted shrink-0">{p.ticker}</span>
                        <div className="flex-1 h-4 rounded bg-surface overflow-hidden">
                          <div className={`h-full rounded ${p.pnl >= 0 ? "bg-green-500/40" : "bg-red-500/40"}`} style={{ width: `${Math.max(width, 2)}%` }} />
                        </div>
                        <span className={`w-16 text-right font-medium shrink-0 ${p.pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                          {p.pnl >= 0 ? "+" : ""}{p.pnl.toFixed(0)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Open positions */}
          {data.positions.length > 0 && (
            <div className="mt-4 rounded-xl border border-border bg-surface-card p-4">
              <h3 className="mb-3 font-bold text-text-primary">{isRu ? "Открытые позиции" : "Open Positions"}</h3>
              <div className="space-y-2">
                {data.positions.map(p => (
                  <div key={p.id} className="flex items-center justify-between rounded-lg bg-surface p-3">
                    <div className="flex items-center gap-3">
                      <span className="font-bold text-text-primary">{p.ticker}</span>
                      <span className={`rounded px-2 py-0.5 text-xs font-bold uppercase ${p.action === "buy" ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"}`}>
                        {p.action}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-sm">
                      <span className="text-text-muted">Entry: {p.entry_price}</span>
                      <span className="text-text-muted">Qty: {p.quantity}</span>
                      <span className="font-medium text-text-primary">{p.value.toLocaleString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* ═══ EXCHANGES TAB ═══ */}
      {tab === "accounts" && (
        <>
          <div className="mb-4 flex justify-end">
            <button onClick={() => setShowForm(!showForm)} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
              {showForm ? (isRu ? "Отмена" : "Cancel") : (isRu ? "+ Подключить биржу" : "+ Connect Exchange")}
            </button>
          </div>

          {showForm && (
            <form onSubmit={handleAddAccount} className="mb-6 space-y-3 rounded-xl border border-border bg-surface-card p-6">
              {formError && <div className="rounded-lg bg-red-500/10 p-3 text-sm text-red-400">{formError}</div>}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs text-text-secondary">{isRu ? "Биржа" : "Exchange"}</label>
                  <select value={formExchange} onChange={(e) => setFormExchange(e.target.value)} className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary">
                    <optgroup label={isRu ? "Демо" : "Paper"}>
                      <option value="demo">Demo (Paper Trading)</option>
                    </optgroup>
                    <optgroup label="Crypto">
                      <option value="binance">Binance</option>
                      <option value="bybit">Bybit</option>
                      <option value="okx">OKX</option>
                      <option value="kraken">Kraken</option>
                    </optgroup>
                    <optgroup label="Forex">
                      <option value="metatrader5">MetaTrader 5</option>
                      <option value="interactive_brokers">Interactive Brokers</option>
                    </optgroup>
                    <optgroup label={isRu ? "Акции" : "Stocks"}>
                      <option value="tinkoff">Tinkoff Invest</option>
                      <option value="exante">Exante</option>
                    </optgroup>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs text-text-secondary">{isRu ? "Название" : "Label"}</label>
                  <input type="text" value={formLabel} onChange={(e) => setFormLabel(e.target.value)} placeholder="My Account"
                    className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-500" />
                </div>
              </div>
              {formExchange !== "demo" && (
                <div className="grid grid-cols-2 gap-3">
                  <div><label className="mb-1 block text-xs text-text-secondary">API Key</label><input type="password" value={formKey} onChange={(e) => setFormKey(e.target.value)} className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none" /></div>
                  <div><label className="mb-1 block text-xs text-text-secondary">API Secret</label><input type="password" value={formSecret} onChange={(e) => setFormSecret(e.target.value)} className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none" /></div>
                </div>
              )}
              <label className="flex items-center gap-2 text-sm text-text-secondary">
                <input type="checkbox" checked={formAuto} onChange={(e) => setFormAuto(e.target.checked)} className="rounded" />
                {isRu ? "Авто-исполнение сигналов" : "Auto-execute signals"}
              </label>
              <button type="submit" className="rounded-lg bg-brand-600 px-6 py-2 text-sm font-medium text-white hover:bg-brand-700">
                {isRu ? "Подключить" : "Connect"}
              </button>
            </form>
          )}

          {accounts.length === 0 ? (
            <div className="rounded-xl border border-border bg-surface-card p-8 text-center text-text-secondary">
              {isRu ? "Нет подключённых бирж. Нажмите \"+ Подключить биржу\" для начала." : "No connected exchanges. Click \"+ Connect Exchange\" to start."}
            </div>
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
                    <span className={acc.auto_execute ? "text-green-400" : "text-text-muted"}>
                      {acc.auto_execute ? (isRu ? "Авто" : "Auto") : (isRu ? "Ручной" : "Manual")}
                    </span>
                    <span className="text-text-muted">WEF {">"}= {(acc.min_confidence * 100).toFixed(0)}%</span>
                    <span className="text-text-muted">{isRu ? "Размер" : "Size"}: {acc.max_position_pct}%</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* ═══ ORDERS TAB ═══ */}
      {tab === "orders" && (
        <>
          {/* Active orders */}
          {activeOrders.length > 0 && (
            <div className="mb-6">
              <h2 className="mb-3 text-lg font-bold text-yellow-400">{isRu ? "Активные ордера" : "Active Orders"} ({activeOrders.length})</h2>
              <div className="overflow-x-auto rounded-xl border border-border">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-border bg-surface-card text-text-muted">
                    <tr>
                      <th className="p-3">{isRu ? "Тикер" : "Symbol"}</th>
                      <th className="p-3">{isRu ? "Сторона" : "Side"}</th>
                      <th className="p-3">{isRu ? "Объём" : "Qty"}</th>
                      <th className="p-3">{isRu ? "Цена" : "Price"}</th>
                      <th className="p-3">{isRu ? "Статус" : "Status"}</th>
                      <th className="p-3">{isRu ? "Биржа" : "Exchange"}</th>
                      <th className="p-3">{isRu ? "Время" : "Time"}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {activeOrders.map((o) => (
                      <tr key={o.id} className="bg-surface-card">
                        <td className="p-3 font-medium text-text-primary">{o.symbol}</td>
                        <td className={`p-3 font-bold uppercase ${o.side === "buy" ? "text-green-400" : "text-red-400"}`}>
                          {o.side === "buy" ? (isRu ? "Покупка" : "Buy") : (isRu ? "Продажа" : "Sell")}
                        </td>
                        <td className="p-3 text-text-secondary">{o.quantity}</td>
                        <td className="p-3 text-text-secondary">{o.filled_price ? formatPrice(o.filled_price) : "—"}</td>
                        <td className="p-3"><span className={`rounded px-2 py-0.5 text-xs ${STATUS_COLOR[o.status] || ""}`}>{isRu ? (STATUS_RU[o.status] || o.status) : o.status}</span></td>
                        <td className="p-3 text-text-muted">{o.exchange}</td>
                        <td className="p-3 text-text-muted">{timeAgo(o.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Completed orders */}
          <h2 className="mb-3 text-lg font-bold text-text-primary">
            {isRu ? "История ордеров" : "Order History"} ({completedOrders.length})
          </h2>
          {completedOrders.length === 0 ? (
            <div className="rounded-xl border border-border bg-surface-card p-8 text-center">
              <p className="text-text-muted">{isRu ? "Нет завершённых ордеров" : "No completed orders"}</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-border">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border bg-surface-card text-text-muted">
                  <tr>
                    <th className="p-3">{isRu ? "Тикер" : "Symbol"}</th>
                    <th className="p-3">{isRu ? "Сторона" : "Side"}</th>
                    <th className="p-3">{isRu ? "Объём" : "Qty"}</th>
                    <th className="p-3">{isRu ? "Цена исп." : "Fill Price"}</th>
                    <th className="p-3">{isRu ? "Статус" : "Status"}</th>
                    <th className="p-3">{isRu ? "Биржа" : "Exchange"}</th>
                    <th className="p-3">{isRu ? "Время" : "Time"}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {completedOrders.map((o) => (
                    <tr key={o.id} className="bg-surface-card">
                      <td className="p-3 font-medium text-text-primary">{o.symbol}</td>
                      <td className={`p-3 font-bold uppercase ${o.side === "buy" ? "text-green-400" : "text-red-400"}`}>
                        {o.side === "buy" ? (isRu ? "Покупка" : "Buy") : (isRu ? "Продажа" : "Sell")}
                      </td>
                      <td className="p-3 text-text-secondary">{o.quantity}</td>
                      <td className="p-3 text-text-secondary">{o.filled_price ? formatPrice(o.filled_price) : "—"}</td>
                      <td className="p-3"><span className={`rounded px-2 py-0.5 text-xs ${STATUS_COLOR[o.status] || ""}`}>{isRu ? (STATUS_RU[o.status] || o.status) : o.status}</span></td>
                      <td className="p-3 text-text-muted">{o.exchange}</td>
                      <td className="p-3 text-text-muted">{timeAgo(o.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {orders.length === 0 && activeOrders.length === 0 && (
            <div className="rounded-xl border border-border bg-surface-card p-8 text-center">
              <p className="text-text-muted">{isRu ? "Нет ордеров. Подключите биржу и начните торговать." : "No orders. Connect an exchange and start trading."}</p>
            </div>
          )}
        </>
      )}

      {/* ═══ JOURNAL TAB ═══ */}
      {tab === "journal" && <JournalPage />}

      {/* ═══ COPY TRADING TAB ═══ */}
      {tab === "copy-trading" && <CopyTradingPage />}
    </div>
  );
}
