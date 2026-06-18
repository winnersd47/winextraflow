"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";

interface Alert {
  id: string; ticker: string; condition: string; target_price: number;
  note: string | null; is_active: boolean; is_triggered: boolean;
  triggered_at: string | null; created_at: string | null;
}

const POPULAR_TICKERS = ["SBER", "GAZP", "BTCUSDT", "ETHUSDT", "LKOH", "AAPL", "NVDA"];

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [ticker, setTicker] = useState("");
  const [condition, setCondition] = useState("above");
  const [price, setPrice] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const { locale } = useI18n();
  const isRu = locale === "ru";

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const load = async () => {
    try {
      const resp = await fetch("/api/v1/alerts?active_only=false", { headers });
      if (resp.ok) { const d = await resp.json(); setAlerts(d.items || []); }
    } catch {}
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    if (!ticker || !price) return;
    setSaving(true);
    try {
      await fetch("/api/v1/alerts", {
        method: "POST", headers,
        body: JSON.stringify({ ticker, condition, target_price: parseFloat(price), note: note || null }),
      });
      setShowForm(false); setTicker(""); setPrice(""); setNote("");
      load();
    } catch {}
    finally { setSaving(false); }
  };

  const handleDelete = async (id: string) => {
    await fetch(`/api/v1/alerts/${id}`, { method: "DELETE", headers });
    load();
  };

  const handleToggle = async (id: string) => {
    await fetch(`/api/v1/alerts/${id}/toggle`, { method: "PATCH", headers });
    load();
  };

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;

  const active = alerts.filter(a => a.is_active && !a.is_triggered);
  const triggered = alerts.filter(a => a.is_triggered);
  const inactive = alerts.filter(a => !a.is_active && !a.is_triggered);

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">{isRu ? "Ценовые алерты" : "Price Alerts"}</h1>
          <p className="text-sm text-text-secondary">{active.length} {isRu ? "активных" : "active"}</p>
        </div>
        <button onClick={() => setShowForm(!showForm)}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
          {showForm ? (isRu ? "Отмена" : "Cancel") : (isRu ? "+ Новый алерт" : "+ New Alert")}
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="mb-4 rounded-xl border border-border bg-surface-card p-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div>
              <input value={ticker} onChange={e => setTicker(e.target.value.toUpperCase())}
                placeholder={isRu ? "Тикер" : "Ticker"}
                className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none" />
              <div className="mt-1 flex flex-wrap gap-1">
                {POPULAR_TICKERS.map(t => (
                  <button key={t} onClick={() => setTicker(t)}
                    className="rounded bg-surface-hover px-1.5 py-0.5 text-xs text-text-muted hover:text-brand-500">{t}</button>
                ))}
              </div>
            </div>
            <select value={condition} onChange={e => setCondition(e.target.value)}
              className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary h-fit">
              <option value="above">{isRu ? "Выше (>)" : "Above (>)"}</option>
              <option value="below">{isRu ? "Ниже (<)" : "Below (<)"}</option>
            </select>
            <input value={price} onChange={e => setPrice(e.target.value)} type="number" step="any"
              placeholder={isRu ? "Целевая цена" : "Target price"}
              className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none" />
            <input value={note} onChange={e => setNote(e.target.value)}
              placeholder={isRu ? "Заметка (опц.)" : "Note (opt.)"}
              className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none" />
          </div>
          <button onClick={handleCreate} disabled={saving || !ticker || !price}
            className="mt-3 rounded-lg bg-brand-600 px-6 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">
            {saving ? "..." : (isRu ? "Создать алерт" : "Create Alert")}
          </button>
        </div>
      )}

      {/* Active alerts */}
      {active.length > 0 && (
        <div className="mb-4">
          <h2 className="mb-2 text-sm font-bold text-text-muted">{isRu ? "Активные" : "Active"} ({active.length})</h2>
          <div className="space-y-2">
            {active.map(a => (
              <div key={a.id} className="flex items-center justify-between rounded-xl border border-border bg-surface-card p-4">
                <div className="flex items-center gap-3">
                  <span className="text-lg font-bold text-text-primary">{a.ticker}</span>
                  <span className={`rounded px-2 py-0.5 text-xs font-bold ${a.condition === "above" ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"}`}>
                    {a.condition === "above" ? ">" : "<"} {a.target_price}
                  </span>
                  {a.note && <span className="text-xs text-text-muted">{a.note}</span>}
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => handleToggle(a.id)} className="rounded px-2 py-1 text-xs text-yellow-400 hover:bg-yellow-500/10">
                    {isRu ? "Пауза" : "Pause"}
                  </button>
                  <button onClick={() => handleDelete(a.id)} className="rounded px-2 py-1 text-xs text-red-400 hover:bg-red-500/10">✕</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Triggered */}
      {triggered.length > 0 && (
        <div className="mb-4">
          <h2 className="mb-2 text-sm font-bold text-green-400">{isRu ? "Сработавшие" : "Triggered"} ({triggered.length})</h2>
          <div className="space-y-2">
            {triggered.map(a => (
              <div key={a.id} className="flex items-center justify-between rounded-xl border border-green-500/30 bg-green-500/5 p-4">
                <div className="flex items-center gap-3">
                  <span className="font-bold text-text-primary">{a.ticker}</span>
                  <span className="text-xs text-green-400">{a.condition === "above" ? ">" : "<"} {a.target_price}</span>
                  {a.triggered_at && <span className="text-xs text-text-muted">{new Date(a.triggered_at).toLocaleDateString()}</span>}
                </div>
                <button onClick={() => handleDelete(a.id)} className="text-xs text-text-muted hover:text-red-400">✕</button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Inactive */}
      {inactive.length > 0 && (
        <div>
          <h2 className="mb-2 text-sm font-bold text-text-muted">{isRu ? "На паузе" : "Paused"} ({inactive.length})</h2>
          <div className="space-y-2">
            {inactive.map(a => (
              <div key={a.id} className="flex items-center justify-between rounded-xl border border-border bg-surface-card/50 p-4 opacity-60">
                <div className="flex items-center gap-3">
                  <span className="font-bold text-text-primary">{a.ticker}</span>
                  <span className="text-xs text-text-muted">{a.condition === "above" ? ">" : "<"} {a.target_price}</span>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => handleToggle(a.id)} className="rounded px-2 py-1 text-xs text-brand-500 hover:bg-brand-500/10">
                    {isRu ? "Включить" : "Activate"}
                  </button>
                  <button onClick={() => handleDelete(a.id)} className="text-xs text-text-muted hover:text-red-400">✕</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {alerts.length === 0 && (
        <div className="rounded-xl border border-border bg-surface-card p-8 text-center">
          <p className="text-lg font-bold text-text-primary mb-2">{isRu ? "Нет алертов" : "No alerts"}</p>
          <p className="text-sm text-text-muted">{isRu ? 'Нажмите "+ Новый алерт" чтобы отслеживать цену' : 'Click "+ New Alert" to track a price'}</p>
        </div>
      )}
    </div>
  );
}
