"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import type { Provider } from "@/types";

export default function TelegramPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const { t, locale } = useI18n();
  const { user } = useAuth();
  const isRu = locale === "ru";
  const canManage = user?.role === "analyst" || user?.role === "admin";

  const [username, setUsername] = useState("");
  const [resolving, setResolving] = useState(false);
  const [resolved, setResolved] = useState<{ id: string; title: string } | null>(null);
  const [providerName, setProviderName] = useState("");
  const [error, setError] = useState("");
  const [subscribing, setSubscribing] = useState(false);

  const load = async () => {
    try {
      const data = await api.getProviders();
      setProviders(data.items.filter((p) => p.source === "telegram"));
    } catch {}
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleResolve = async () => {
    if (!username.trim()) return;
    setResolving(true);
    setError("");
    setResolved(null);
    try {
      const result = await api.resolveTelegramChannel(username);
      setResolved(result);
      setProviderName(result.title || username);
    } catch (err: any) {
      setError(err.message || (isRu ? "Не удалось найти канал" : "Could not resolve channel"));
    } finally { setResolving(false); }
  };

  const handleSubscribe = async () => {
    setSubscribing(true);
    setError("");
    try {
      const provider = await api.createProvider({
        name: providerName || username,
        source: "telegram",
        description: `Telegram: ${resolved?.title || username}`,
      });
      if (resolved) {
        await api.subscribeTelegram(provider.id, { channel_id: resolved.id, channel_name: resolved.title });
      } else {
        await api.subscribeTelegram(provider.id, { channel_username: username });
      }
      setShowForm(false);
      setUsername("");
      setResolved(null);
      setProviderName("");
      load();
    } catch (err: any) {
      setError(err.message || (isRu ? "Ошибка подключения" : "Failed to subscribe"));
    } finally { setSubscribing(false); }
  };

  const handleDisconnect = async (providerId: string) => {
    try { await api.unsubscribeTelegram(providerId); load(); } catch {}
  };

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;

  // Non-analysts see explanation
  if (!canManage) {
    return (
      <div className="mx-auto max-w-2xl py-12">
        <div className="rounded-2xl border border-border bg-surface-card p-8 text-center">
          <h1 className="mb-4 text-2xl font-bold text-text-primary">
            {isRu ? "Telegram-каналы" : "Telegram Channels"}
          </h1>
          <p className="mb-4 text-text-secondary">
            {isRu
              ? "Этот раздел предназначен для аналитиков — сотрудников, которые подключают Telegram-каналы как источники торговых сигналов. Система автоматически парсит сообщения из каналов и создаёт сигналы на платформе."
              : "This section is for analysts — employees who connect Telegram channels as trading signal sources. The system automatically parses channel messages and creates signals on the platform."}
          </p>
          <div className="mb-6 rounded-lg bg-surface p-4 text-left">
            <p className="mb-2 text-sm font-bold text-text-primary">{isRu ? "Как это работает:" : "How it works:"}</p>
            <ul className="space-y-1 text-sm text-text-secondary">
              <li>1. {isRu ? "Аналитик подключает Telegram-канал с торговыми сигналами" : "Analyst connects a Telegram channel with trading signals"}</li>
              <li>2. {isRu ? "Система мониторит сообщения и распознаёт BUY/SELL сигналы" : "System monitors messages and recognizes BUY/SELL signals"}</li>
              <li>3. {isRu ? "Сигналы автоматически появляются на платформе с AI-оценкой" : "Signals automatically appear on the platform with AI rating"}</li>
              <li>4. {isRu ? "Вы видите их в разделе Сигналы и Аналитика" : "You see them in Signals and Intelligence sections"}</li>
            </ul>
          </div>
          <p className="mb-4 text-sm text-text-secondary">
            {isRu
              ? "Для получения сигналов в Telegram напрямую — подключите Telegram-бот в Профиле или купите Premium для доступа к VIP-каналу."
              : "To receive signals in Telegram directly — connect the Telegram bot in Profile or buy Premium for VIP channel access."}
          </p>
          <div className="flex justify-center gap-3">
            <a href="/dashboard/profile" className="rounded-lg bg-brand-600 px-6 py-2 text-sm font-medium text-white hover:bg-brand-700">
              {isRu ? "Подключить бот в профиле" : "Connect bot in profile"}
            </a>
            <a href="/dashboard/store" className="rounded-lg border border-border px-6 py-2 text-sm text-text-secondary hover:bg-surface-hover">
              {isRu ? "VIP-канал в магазине" : "VIP channel in store"}
            </a>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">{isRu ? "Управление Telegram-каналами" : "Telegram Channel Management"}</h1>
          <p className="text-sm text-text-secondary">
            {isRu ? "Подключение каналов как источников сигналов. Только для аналитиков." : "Connect channels as signal sources. Analysts only."}
          </p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
          {showForm ? (isRu ? "Отмена" : "Cancel") : (isRu ? "+ Добавить канал" : "+ Add Channel")}
        </button>
      </div>

      {/* Explanation */}
      <div className="mb-6 rounded-lg border border-border bg-surface-card p-4">
        <p className="text-xs text-text-muted">
          {isRu
            ? "Канал — это источник сигналов (провайдер). После подключения система автоматически парсит сообщения и создаёт сигналы на платформе. Требуется настройка TELEGRAM_API_ID и TELEGRAM_API_HASH в .env."
            : "A channel is a signal source (provider). After connecting, the system automatically parses messages and creates signals. Requires TELEGRAM_API_ID and TELEGRAM_API_HASH in .env."}
        </p>
      </div>

      {/* Add Channel Form */}
      {showForm && (
        <div className="mb-6 rounded-xl border border-border bg-surface-card p-6 space-y-4">
          {error && <div className="rounded-lg bg-red-500/10 p-3 text-sm text-red-400">{error}</div>}
          <div>
            <label className="mb-1 block text-sm text-text-secondary">{isRu ? "Юзернейм канала" : "Channel username"}</label>
            <div className="flex gap-2">
              <input type="text" value={username} onChange={(e) => { setUsername(e.target.value); setResolved(null); }}
                placeholder="@channel_name" className="flex-1 rounded-lg border border-border bg-surface px-4 py-2.5 text-text-primary outline-none focus:border-brand-500" />
              <button onClick={handleResolve} disabled={resolving || !username.trim()} className="rounded-lg bg-surface-hover px-4 py-2.5 text-sm font-medium text-text-primary hover:bg-brand-500/20 disabled:opacity-50">
                {resolving ? "..." : (isRu ? "Найти" : "Resolve")}
              </button>
            </div>
          </div>
          {resolved && (
            <div className="rounded-lg bg-green-500/10 border border-green-500/30 p-4">
              <p className="text-sm font-medium text-green-400">{isRu ? "Канал найден" : "Channel found"}</p>
              <p className="text-text-primary font-semibold">{resolved.title}</p>
              <p className="text-xs text-text-muted">ID: {resolved.id}</p>
            </div>
          )}
          {(resolved || username.trim()) && (
            <div>
              <label className="mb-1 block text-sm text-text-secondary">{isRu ? "Название провайдера" : "Provider name"}</label>
              <input type="text" value={providerName} onChange={(e) => setProviderName(e.target.value)}
                placeholder={resolved?.title || username}
                className="w-full rounded-lg border border-border bg-surface px-4 py-2.5 text-text-primary outline-none focus:border-brand-500" />
              <button onClick={handleSubscribe} disabled={subscribing} className="mt-3 rounded-lg bg-brand-600 px-6 py-2.5 font-medium text-white hover:bg-brand-700 disabled:opacity-50">
                {subscribing ? "..." : (isRu ? "Подключить канал" : "Connect Channel")}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Channel List */}
      {providers.length === 0 ? (
        <div className="rounded-xl border border-border bg-surface-card p-12 text-center">
          <p className="text-text-secondary">{isRu ? "Нет подключённых каналов" : "No connected channels"}</p>
          <p className="mt-1 text-sm text-text-muted">{isRu ? "Нажмите «+ Добавить канал» чтобы подключить источник сигналов." : "Click '+ Add Channel' to connect a signal source."}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {providers.map((p) => (
            <div key={p.id} className="flex items-center justify-between rounded-xl border border-border bg-surface-card p-4">
              <div>
                <h3 className="font-semibold text-text-primary">{p.name}</h3>
                <p className="text-xs text-text-muted">{p.description} | {p.total_signals} {isRu ? "сигналов" : "signals"}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`rounded px-2 py-0.5 text-xs font-bold ${p.is_active ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
                  {p.is_active ? (isRu ? "Подключён" : "Connected") : (isRu ? "Отключён" : "Disconnected")}
                </span>
                {p.is_active && (
                  <button onClick={() => handleDisconnect(p.id)} className="text-sm text-red-400 hover:text-red-300">
                    {isRu ? "Отключить" : "Disconnect"}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
