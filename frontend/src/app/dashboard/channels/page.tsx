"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

interface DiscoveredChannel {
  username: string;
  title: string;
  subscribers: number | null;
  signal_like: number;
  parsed: number;
  yield_pct: number;
  tier: string;
  sample: string;
  monitored?: boolean;
}

const MARKET_LABELS: Record<string, { ru: string; en: string; icon: string }> = {
  moex: { ru: "Акции РФ", en: "RU Stocks", icon: "🇷🇺" },
  crypto: { ru: "Криптовалюта", en: "Crypto", icon: "₿" },
  forex: { ru: "Форекс", en: "Forex", icon: "💱" },
  stocks_us: { ru: "Акции США", en: "US Stocks", icon: "🇺🇸" },
  commodities: { ru: "Сырьё", en: "Commodities", icon: "🥇" },
};

const TIER_BADGE: Record<string, { label: string; cls: string }> = {
  signals: { label: "Сигналы", cls: "bg-green-500/15 text-green-400" },
  format_mismatch: { label: "Формат ?", cls: "bg-yellow-500/15 text-yellow-400" },
  mostly_news: { label: "Новости", cls: "bg-gray-500/15 text-gray-400" },
};

function authHeaders() {
  return { Authorization: `Bearer ${typeof window !== "undefined" ? localStorage.getItem("token") : ""}` };
}

export default function ChannelsPage() {
  const { locale } = useI18n();
  const { user } = useAuth();
  const isRu = locale === "ru";
  const isAdmin = user?.role === "admin";

  const [market, setMarket] = useState("crypto");
  const [discovered, setDiscovered] = useState<DiscoveredChannel[]>([]);
  const [monitored, setMonitored] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [discovering, setDiscovering] = useState(false);
  const [msg, setMsg] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const [disc, mon] = await Promise.all([
        fetch(`/api/v1/channels/discovered?market=${market}`, { headers: authHeaders() }).then(r => r.json()),
        fetch(`/api/v1/channels/monitored`, { headers: authHeaders() }).then(r => r.json()),
      ]);
      setDiscovered(disc.channels || []);
      setMonitored(mon.channels || []);
    } catch { }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [market]);

  const runDiscover = async () => {
    setDiscovering(true);
    setMsg(isRu ? "Поиск каналов через Telegram... (до 1 мин)" : "Searching Telegram... (up to 1 min)");
    try {
      const r = await fetch(`/api/v1/channels/discover?market=${market}`, { method: "POST", headers: authHeaders() });
      const d = await r.json();
      if (d.ok) {
        setMsg(isRu ? `Найдено ${d.total} каналов, готовы к мониторингу: ${d.ready_to_monitor?.length || 0}` : `Found ${d.total}, ready: ${d.ready_to_monitor?.length || 0}`);
        await load();
      } else {
        setMsg(d.detail || "Error");
      }
    } catch (e: any) { setMsg(e.message || "Error"); }
    finally { setDiscovering(false); }
  };

  const addChannel = async (username: string) => {
    await fetch(`/api/v1/channels/monitored`, {
      method: "POST", headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ username }),
    });
    await load();
  };

  const removeChannel = async (username: string) => {
    await fetch(`/api/v1/channels/monitored/${username}`, { method: "DELETE", headers: authHeaders() });
    await load();
  };

  const isMonitored = (u: string) => monitored.some(m => m.toLowerCase() === u.toLowerCase());

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text-primary">{isRu ? "Поиск каналов" : "Channel Discovery"}</h1>
        <p className="mt-1 text-sm text-text-muted">
          {isRu
            ? "Поиск сигнальных каналов Telegram по всем рынкам через телефон + оценка парсером"
            : "Search Telegram signal channels across all markets via phone + parser scoring"}
        </p>
      </div>

      {/* Market tabs */}
      <div className="mb-4 flex flex-wrap gap-2">
        {Object.entries(MARKET_LABELS).map(([key, m]) => (
          <button key={key} onClick={() => setMarket(key)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${market === key ? "bg-brand-600 text-white" : "bg-surface-card text-text-secondary hover:bg-surface"}`}>
            {m.icon} {isRu ? m.ru : m.en}
          </button>
        ))}
      </div>

      {/* Discover action */}
      {isAdmin && (
        <div className="mb-4 flex items-center gap-3">
          <button onClick={runDiscover} disabled={discovering}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">
            {discovering ? (isRu ? "Поиск..." : "Searching...") : (isRu ? "🔍 Найти каналы" : "🔍 Discover")}
          </button>
          {msg && <span className="text-sm text-text-muted">{msg}</span>}
        </div>
      )}

      {/* Monitored channels */}
      <div className="mb-6 rounded-xl border border-border bg-surface-card p-4">
        <h2 className="mb-3 text-sm font-bold text-text-primary">
          {isRu ? "Мониторятся" : "Monitored"} ({monitored.length})
        </h2>
        <div className="flex flex-wrap gap-2">
          {monitored.map(m => (
            <span key={m} className="inline-flex items-center gap-1.5 rounded-full bg-brand-500/10 px-3 py-1 text-xs text-brand-400">
              @{m}
              {isAdmin && (
                <button onClick={() => removeChannel(m)} className="text-red-400 hover:text-red-300" title="Remove">✕</button>
              )}
            </span>
          ))}
          {monitored.length === 0 && <span className="text-sm text-text-muted">{isRu ? "Пусто" : "None"}</span>}
        </div>
      </div>

      {/* Discovered list */}
      <div className="rounded-xl border border-border bg-surface-card">
        <div className="border-b border-border px-4 py-3">
          <h2 className="text-sm font-bold text-text-primary">
            {isRu ? "Найденные каналы" : "Discovered"} — {MARKET_LABELS[market] ? (isRu ? MARKET_LABELS[market].ru : MARKET_LABELS[market].en) : market}
          </h2>
        </div>
        {loading ? (
          <div className="p-8 text-center text-text-muted">{isRu ? "Загрузка..." : "Loading..."}</div>
        ) : discovered.length === 0 ? (
          <div className="p-8 text-center text-text-muted">
            {isRu ? "Нет данных. Нажмите «Найти каналы»." : "No data. Click Discover."}
          </div>
        ) : (
          <div className="divide-y divide-border">
            {discovered.map(c => {
              const badge = TIER_BADGE[c.tier] || TIER_BADGE.mostly_news;
              const mon = isMonitored(c.username);
              return (
                <div key={c.username} className="flex items-center justify-between gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-medium text-text-primary">{c.title}</span>
                      <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${badge.cls}`}>{badge.label}</span>
                    </div>
                    <div className="mt-0.5 flex flex-wrap items-center gap-x-3 text-xs text-text-muted">
                      <span>@{c.username}</span>
                      {c.subscribers != null && <span>{(c.subscribers / 1000).toFixed(0)}k подп.</span>}
                      <span>yield {c.yield_pct}%</span>
                      <span>{c.parsed}/{c.signal_like} сигн.</span>
                    </div>
                    {c.sample && <div className="mt-0.5 truncate text-xs text-brand-400">e.g. {c.sample}</div>}
                  </div>
                  {isAdmin && (
                    mon ? (
                      <button onClick={() => removeChannel(c.username)}
                        className="shrink-0 rounded-lg bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-400 hover:bg-red-500/20">
                        {isRu ? "Убрать" : "Remove"}
                      </button>
                    ) : (
                      <button onClick={() => addChannel(c.username)}
                        className="shrink-0 rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-700">
                        {isRu ? "+ Мониторить" : "+ Monitor"}
                      </button>
                    )
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <p className="mt-4 text-xs text-text-muted">
        {isRu
          ? "Добавленные каналы автоматически парсятся поллером (каждые 30 мин) и сигналы уходят в VIP."
          : "Monitored channels are auto-parsed by the poller (every 30 min); signals go to VIP."}
      </p>
    </div>
  );
}
