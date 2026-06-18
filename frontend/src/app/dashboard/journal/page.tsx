"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";

interface JournalEntry {
  id: string; ticker: string; action: string; entry_price: number;
  exit_price: number | null; quantity: number | null; profit_pct: number | null;
  profit_abs: number | null; note: string | null; tags: string[];
  emotion: string | null; rating: number | null; opened_at: string | null;
  closed_at: string | null;
}
interface Stats {
  total_trades: number; closed_trades: number; wins: number; losses: number;
  win_rate: number; avg_profit_pct: number; best_trade_pct: number;
  worst_trade_pct: number; total_profit_abs: number;
  top_tickers: { ticker: string; trades: number; win_rate: number; avg_pct: number }[];
}

const EMOTIONS = [
  { key: "disciplined", ru: "Дисциплина", en: "Disciplined", emoji: "🎯" },
  { key: "confident", ru: "Уверенность", en: "Confident", emoji: "💪" },
  { key: "nervous", ru: "Нервозность", en: "Nervous", emoji: "😰" },
  { key: "fomo", ru: "FOMO", en: "FOMO", emoji: "🏃" },
  { key: "revenge", ru: "Реванш", en: "Revenge", emoji: "😤" },
];

export default function JournalPage() {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [tab, setTab] = useState<"entries" | "stats">("entries");
  const { locale } = useI18n();
  const isRu = locale === "ru";

  // Form state
  const [ticker, setTicker] = useState("");
  const [action, setAction] = useState("buy");
  const [entryPrice, setEntryPrice] = useState("");
  const [exitPrice, setExitPrice] = useState("");
  const [quantity, setQuantity] = useState("");
  const [note, setNote] = useState("");
  const [emotion, setEmotion] = useState("");
  const [saving, setSaving] = useState(false);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const load = async () => {
    try {
      const [eResp, sResp] = await Promise.all([
        fetch("/api/v1/journal?limit=100", { headers }),
        fetch("/api/v1/journal/stats", { headers }),
      ]);
      if (eResp.ok) { const d = await eResp.json(); setEntries(d.items || []); }
      if (sResp.ok) { setStats(await sResp.json()); }
    } catch {}
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    if (!ticker || !entryPrice) return;
    setSaving(true);
    try {
      const resp = await fetch("/api/v1/journal", {
        method: "POST", headers,
        body: JSON.stringify({
          ticker, action, entry_price: parseFloat(entryPrice),
          exit_price: exitPrice ? parseFloat(exitPrice) : null,
          quantity: quantity ? parseFloat(quantity) : null,
          note: note || null, emotion: emotion || null,
        }),
      });
      if (resp.ok) {
        setShowForm(false);
        setTicker(""); setEntryPrice(""); setExitPrice(""); setQuantity(""); setNote(""); setEmotion("");
        load();
      }
    } catch {}
    finally { setSaving(false); }
  };

  const handleDelete = async (id: string) => {
    await fetch(`/api/v1/journal/${id}`, { method: "DELETE", headers });
    load();
  };

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">{isRu ? "Торговый журнал" : "Trading Journal"}</h1>
          <p className="text-sm text-text-secondary">{entries.length} {isRu ? "записей" : "entries"}</p>
        </div>
        <button onClick={() => setShowForm(!showForm)}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
          {showForm ? (isRu ? "Отмена" : "Cancel") : (isRu ? "+ Новая сделка" : "+ New Trade")}
        </button>
      </div>

      {/* New trade form */}
      {showForm && (
        <div className="mb-4 rounded-xl border border-border bg-surface-card p-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <input placeholder={isRu ? "Тикер" : "Ticker"} value={ticker} onChange={e => setTicker(e.target.value)}
              className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none" />
            <select value={action} onChange={e => setAction(e.target.value)}
              className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary">
              <option value="buy">BUY</option>
              <option value="sell">SELL</option>
            </select>
            <input placeholder={isRu ? "Цена входа" : "Entry price"} value={entryPrice} onChange={e => setEntryPrice(e.target.value)} type="number" step="any"
              className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none" />
            <input placeholder={isRu ? "Цена выхода (опц.)" : "Exit price (opt.)"} value={exitPrice} onChange={e => setExitPrice(e.target.value)} type="number" step="any"
              className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none" />
            <input placeholder={isRu ? "Объём (опц.)" : "Quantity (opt.)"} value={quantity} onChange={e => setQuantity(e.target.value)} type="number" step="any"
              className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none" />
            <select value={emotion} onChange={e => setEmotion(e.target.value)}
              className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary">
              <option value="">{isRu ? "Эмоция..." : "Emotion..."}</option>
              {EMOTIONS.map(em => <option key={em.key} value={em.key}>{em.emoji} {isRu ? em.ru : em.en}</option>)}
            </select>
            <input placeholder={isRu ? "Заметка..." : "Note..."} value={note} onChange={e => setNote(e.target.value)}
              className="col-span-2 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none" />
          </div>
          <button onClick={handleCreate} disabled={saving || !ticker || !entryPrice}
            className="mt-3 rounded-lg bg-brand-600 px-6 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">
            {saving ? "..." : (isRu ? "Сохранить" : "Save")}
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="mb-4 flex gap-2">
        <button onClick={() => setTab("entries")}
          className={`rounded-lg px-4 py-2 text-sm font-medium ${tab === "entries" ? "bg-brand-500 text-white" : "text-text-secondary hover:bg-surface-hover"}`}>
          {isRu ? "Сделки" : "Trades"}
        </button>
        <button onClick={() => setTab("stats")}
          className={`rounded-lg px-4 py-2 text-sm font-medium ${tab === "stats" ? "bg-brand-500 text-white" : "text-text-secondary hover:bg-surface-hover"}`}>
          {isRu ? "Статистика" : "Statistics"}
        </button>
      </div>

      {tab === "entries" ? (
        /* Entries list */
        entries.length === 0 ? (
          <div className="rounded-xl border border-border bg-surface-card p-8 text-center">
            <p className="text-text-muted">{isRu ? "Журнал пуст. Добавьте первую сделку!" : "Journal is empty. Add your first trade!"}</p>
          </div>
        ) : (
          <div className="space-y-2">
            {entries.map(e => (
              <div key={e.id} className="rounded-xl border border-border bg-surface-card p-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <span className="text-lg font-bold text-text-primary">{e.ticker}</span>
                    <span className={`rounded px-2 py-0.5 text-xs font-bold uppercase ${e.action === "buy" ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"}`}>
                      {e.action}
                    </span>
                    {e.emotion && (
                      <span className="rounded bg-purple-500/10 px-2 py-0.5 text-xs text-purple-400">
                        {EMOTIONS.find(em => em.key === e.emotion)?.emoji || ""} {e.emotion}
                      </span>
                    )}
                    {e.tags?.map(t => (
                      <span key={t} className="rounded bg-surface-hover px-1.5 py-0.5 text-xs text-text-muted">#{t}</span>
                    ))}
                  </div>
                  <div className="flex items-center gap-2">
                    {e.profit_pct !== null && (
                      <span className={`text-sm font-bold ${e.profit_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {e.profit_pct >= 0 ? "+" : ""}{e.profit_pct.toFixed(1)}%
                      </span>
                    )}
                    <button onClick={() => handleDelete(e.id)} className="text-xs text-text-muted hover:text-red-400">✕</button>
                  </div>
                </div>
                <div className="mt-2 flex gap-4 text-xs text-text-muted">
                  <span>Entry: {e.entry_price}</span>
                  {e.exit_price && <span>Exit: {e.exit_price}</span>}
                  {e.quantity && <span>Qty: {e.quantity}</span>}
                  {e.opened_at && <span>{new Date(e.opened_at).toLocaleDateString()}</span>}
                </div>
                {e.note && <p className="mt-2 text-sm text-text-secondary">{e.note}</p>}
              </div>
            ))}
          </div>
        )
      ) : (
        /* Stats tab */
        stats && (
          <div className="space-y-4">
            {/* Summary cards */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              {[
                { label: isRu ? "Всего сделок" : "Total Trades", value: stats.total_trades, color: "text-text-primary" },
                { label: "Win Rate", value: `${(stats.win_rate * 100).toFixed(0)}%`, color: stats.win_rate >= 0.5 ? "text-green-400" : "text-red-400" },
                { label: isRu ? "Ср. прибыль" : "Avg Profit", value: `${stats.avg_profit_pct >= 0 ? "+" : ""}${stats.avg_profit_pct.toFixed(1)}%`, color: stats.avg_profit_pct >= 0 ? "text-green-400" : "text-red-400" },
                { label: isRu ? "Лучшая" : "Best", value: `+${stats.best_trade_pct.toFixed(1)}%`, color: "text-green-400" },
                { label: isRu ? "Худшая" : "Worst", value: `${stats.worst_trade_pct.toFixed(1)}%`, color: "text-red-400" },
              ].map(s => (
                <div key={s.label} className="rounded-xl border border-border bg-surface-card p-4 text-center">
                  <div className="text-xs text-text-muted">{s.label}</div>
                  <div className={`text-xl font-bold ${s.color}`}>{s.value}</div>
                </div>
              ))}
            </div>

            {/* Top tickers */}
            {stats.top_tickers.length > 0 && (
              <div className="rounded-xl border border-border bg-surface-card p-4">
                <h3 className="mb-3 font-bold text-text-primary">{isRu ? "Лучшие тикеры" : "Top Tickers"}</h3>
                <div className="space-y-2">
                  {stats.top_tickers.map(t => (
                    <div key={t.ticker} className="flex items-center justify-between text-sm">
                      <span className="font-medium text-text-primary">{t.ticker}</span>
                      <div className="flex gap-4 text-xs">
                        <span className="text-text-muted">{t.trades} {isRu ? "сделок" : "trades"}</span>
                        <span className={t.win_rate >= 0.5 ? "text-green-400" : "text-red-400"}>WR: {(t.win_rate * 100).toFixed(0)}%</span>
                        <span className={t.avg_pct >= 0 ? "text-green-400" : "text-red-400"}>{t.avg_pct >= 0 ? "+" : ""}{t.avg_pct.toFixed(1)}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {stats.total_trades === 0 && (
              <div className="rounded-xl border border-border bg-surface-card p-8 text-center">
                <p className="text-text-muted">{isRu ? "Добавьте сделки для отображения статистики" : "Add trades to see statistics"}</p>
              </div>
            )}
          </div>
        )
      )}
    </div>
  );
}
