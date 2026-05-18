"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import type { Provider } from "@/types";

export default function TelegramPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [tgLink, setTgLink] = useState<any>(null);
  const [maxLink, setMaxLink] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showAddChannel, setShowAddChannel] = useState(false);
  const { t, locale } = useI18n();
  const { user } = useAuth();
  const isRu = locale === "ru";
  const canManage = user?.role === "analyst" || user?.role === "admin";

  // Add channel form
  const [username, setUsername] = useState("");
  const [resolving, setResolving] = useState(false);
  const [resolved, setResolved] = useState<{ id: string; title: string } | null>(null);
  const [providerName, setProviderName] = useState("");
  const [error, setError] = useState("");
  const [subscribing, setSubscribing] = useState(false);

  const load = async () => {
    try {
      const [provData, tg, mx] = await Promise.all([
        api.getProviders(),
        api.getTelegramLink().catch(() => null),
        fetch("/api/v1/auth/max-link", { headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } }).then(r => r.ok ? r.json() : null).catch(() => null),
      ]);
      setProviders(provData.items.filter((p) => p.source === "telegram"));
      setTgLink(tg);
      setMaxLink(mx);
    } catch {}
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleResolve = async () => {
    if (!username.trim()) return;
    setResolving(true); setError(""); setResolved(null);
    try {
      const result = await api.resolveTelegramChannel(username);
      setResolved(result);
      setProviderName(result.title || username);
    } catch (err: any) {
      setError(err.message || (isRu ? "Не удалось найти канал" : "Could not resolve channel"));
    } finally { setResolving(false); }
  };

  const handleSubscribe = async () => {
    setSubscribing(true); setError("");
    try {
      const provider = await api.createProvider({ name: providerName || username, source: "telegram", description: `Telegram: ${resolved?.title || username}` });
      if (resolved) { await api.subscribeTelegram(provider.id, { channel_id: resolved.id, channel_name: resolved.title }); }
      else { await api.subscribeTelegram(provider.id, { channel_username: username }); }
      setShowAddChannel(false); setUsername(""); setResolved(null); setProviderName(""); load();
    } catch (err: any) { setError(err.message || (isRu ? "Ошибка подключения" : "Failed")); }
    finally { setSubscribing(false); }
  };

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-2 text-2xl font-bold text-text-primary">
        {isRu ? "Мессенджеры" : "Messengers"}
      </h1>
      <p className="mb-6 text-sm text-text-secondary">
        {isRu
          ? "Подключение ботов для уведомлений, исходящие каналы с сигналами, и источники сигналов."
          : "Bot connections for notifications, outgoing signal channels, and signal sources."}
      </p>

      {/* ═══ SECTION 1: Личные боты (уведомления) ═══ */}
      <div className="mb-8">
        <h2 className="mb-3 flex items-center gap-2 text-lg font-bold text-text-primary">
          {isRu ? "Личные уведомления" : "Personal Notifications"}
        </h2>
        <p className="mb-4 text-sm text-text-secondary">
          {isRu
            ? "Привяжите мессенджер, чтобы получать уведомления о новых сигналах, исполнении сделок и достижениях прямо в личные сообщения."
            : "Link a messenger to receive notifications about new signals, trade executions, and achievements directly in your DMs."}
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          {/* Telegram Bot */}
          <div className="rounded-xl border border-border bg-surface-card p-4">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-bold text-text-primary">Telegram</h3>
              {tgLink?.linked ? (
                <span className="rounded bg-green-500/20 px-2 py-0.5 text-xs font-bold text-green-400">{isRu ? "Подключён" : "Linked"}</span>
              ) : (
                <span className="rounded bg-surface-hover px-2 py-0.5 text-xs text-text-muted">{isRu ? "Не подключён" : "Not linked"}</span>
              )}
            </div>
            <p className="text-xs text-text-muted mb-3">
              {isRu ? "Бот отправляет сигналы, статусы сделок и достижения в личные сообщения Telegram." : "Bot sends signals, trade statuses, and achievements to your Telegram DMs."}
            </p>
            {tgLink?.enabled ? (
              tgLink.linked ? (
                <p className="text-xs text-green-400">{isRu ? "Уведомления активны. Управление — в Профиле." : "Notifications active. Manage in Profile."}</p>
              ) : (
                <a href={tgLink.link || "#"} target="_blank" rel="noopener" className="inline-block rounded-lg bg-brand-600 px-4 py-2 text-xs font-medium text-white hover:bg-brand-700">
                  {isRu ? "Привязать Telegram" : "Link Telegram"}
                </a>
              )
            ) : (
              <p className="text-xs text-text-muted">{isRu ? "Бот не настроен (TELEGRAM_BOT_TOKEN)" : "Bot not configured"}</p>
            )}
          </div>

          {/* MAX Bot */}
          <div className="rounded-xl border border-border bg-surface-card p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-text-primary">MAX</h3>
                <span className="rounded bg-blue-500/10 px-1.5 py-0.5 text-xs text-blue-400">RU</span>
              </div>
              {maxLink?.linked ? (
                <span className="rounded bg-green-500/20 px-2 py-0.5 text-xs font-bold text-green-400">{isRu ? "Подключён" : "Linked"}</span>
              ) : (
                <span className="rounded bg-surface-hover px-2 py-0.5 text-xs text-text-muted">{isRu ? "Не подключён" : "Not linked"}</span>
              )}
            </div>
            <p className="text-xs text-text-muted mb-3">
              {isRu ? "Национальный мессенджер России от VK. Дублирует уведомления из Telegram." : "Russia's national messenger by VK. Mirrors Telegram notifications."}
            </p>
            {maxLink?.enabled ? (
              maxLink.linked ? (
                <p className="text-xs text-green-400">{isRu ? "Уведомления активны." : "Notifications active."}</p>
              ) : (
                <a href={maxLink.link || "#"} target="_blank" rel="noopener" className="inline-block rounded-lg bg-brand-600 px-4 py-2 text-xs font-medium text-white hover:bg-brand-700">
                  {isRu ? "Привязать MAX" : "Link MAX"}
                </a>
              )
            ) : (
              <p className="text-xs text-text-muted">{isRu ? "Бот не настроен (MAX_BOT_TOKEN)" : "Bot not configured"}</p>
            )}
          </div>
        </div>
      </div>

      {/* ═══ SECTION 2: Исходящие каналы (рассылка) ═══ */}
      <div className="mb-8">
        <h2 className="mb-3 text-lg font-bold text-text-primary">
          {isRu ? "Каналы с сигналами" : "Signal Channels"}
        </h2>
        <p className="mb-4 text-sm text-text-secondary">
          {isRu
            ? "Платформа рассылает обработанные сигналы в публичные каналы. VIP-канал получает полные данные мгновенно, бесплатный — только направление через 2 часа."
            : "The platform broadcasts processed signals to public channels. VIP gets full data instantly, free gets direction only after 2 hours."}
        </p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <ChannelCard
            name="@WinExtraFlowSignals"
            platform="Telegram"
            type={isRu ? "Бесплатный" : "Free"}
            typeColor="bg-green-500/20 text-green-400"
            desc={isRu ? "Направление (BUY/SELL), задержка 2ч" : "Direction only, 2h delay"}
            link="https://t.me/WinExtraFlowSignals"
            buttonText={isRu ? "Подписаться" : "Subscribe"}
          />
          <ChannelCard
            name="VIP"
            platform="Telegram"
            type="Premium"
            typeColor="bg-brand-500/20 text-brand-500"
            desc={isRu ? "Вход, TP, SL, AI качество — мгновенно" : "Entry, TP, SL, AI quality — instant"}
            link="https://t.me/+xX-irBLmJddlYTg6"
            buttonText={isRu ? "Войти" : "Enter"}
            isPremium
          />
          <ChannelCard
            name="Signals"
            platform="MAX"
            type={isRu ? "Бесплатный" : "Free"}
            typeColor="bg-green-500/20 text-green-400"
            desc={isRu ? "Дублирует Telegram Free в MAX" : "Mirrors Telegram Free in MAX"}
          />
          <ChannelCard
            name="VIP"
            platform="MAX"
            type="Premium"
            typeColor="bg-brand-500/20 text-brand-500"
            desc={isRu ? "Дублирует Telegram VIP в MAX" : "Mirrors Telegram VIP in MAX"}
          />
        </div>
        <div className="mt-3 rounded-lg bg-surface px-4 py-2 text-xs text-text-muted">
          {isRu
            ? "Схема: новый сигнал → AI-оценка → VIP каналы (мгновенно, полные данные) → бесплатные каналы (через 2ч, только направление)."
            : "Flow: new signal → AI rating → VIP channels (instant, full data) → free channels (2h delay, direction only)."}
        </div>
      </div>

      {/* ═══ SECTION 3: Сообщество ═══ */}
      <div className="mb-8">
        <h2 className="mb-3 text-lg font-bold text-text-primary">
          {isRu ? "Сообщество" : "Community"}
        </h2>
        <div className="rounded-xl border border-border bg-surface-card p-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-bold text-text-primary">AI Growth Club</h3>
              <p className="text-xs text-text-muted">
                {isRu ? "Открытая группа: обсуждения рынка, AI-аналитика, обмен опытом, новости платформы." : "Open group: market discussions, AI analytics, experience sharing, platform news."}
              </p>
            </div>
            <a href="https://t.me/+HEyibcuonz00NTI6" target="_blank" rel="noopener"
              className="flex-shrink-0 rounded-lg border border-border px-4 py-2 text-sm text-text-primary hover:bg-surface-hover">
              {isRu ? "Присоединиться" : "Join"}
            </a>
          </div>
        </div>
      </div>

      {/* ═══ SECTION 4: Входящие источники (только Analyst/Admin) ═══ */}
      {canManage && (
        <div className="mb-8">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="flex items-center gap-2 text-lg font-bold text-text-primary">
                {isRu ? "Источники сигналов" : "Signal Sources"}
                <span className="rounded bg-blue-500/20 px-2 py-0.5 text-xs font-bold text-blue-400">Analyst</span>
              </h2>
              <p className="mt-1 text-sm text-text-secondary">
                {isRu
                  ? "Подключённые Telegram-каналы, из которых платформа автоматически парсит торговые сигналы. Система распознаёт BUY/SELL, тикер, цену, TP/SL из сообщений и создаёт сигналы с AI-оценкой."
                  : "Connected Telegram channels from which the platform auto-parses trading signals. The system recognizes BUY/SELL, ticker, price, TP/SL from messages and creates AI-rated signals."}
              </p>
            </div>
            <button onClick={() => setShowAddChannel(!showAddChannel)} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
              {showAddChannel ? (isRu ? "Отмена" : "Cancel") : (isRu ? "+ Добавить" : "+ Add")}
            </button>
          </div>

          {/* Add Channel Form */}
          {showAddChannel && (
            <div className="mb-4 rounded-xl border border-border bg-surface-card p-6 space-y-4">
              {error && <div className="rounded-lg bg-red-500/10 p-3 text-sm text-red-400">{error}</div>}
              <div>
                <label className="mb-1 block text-sm text-text-secondary">{isRu ? "Юзернейм канала" : "Channel username"}</label>
                <div className="flex gap-2">
                  <input type="text" value={username} onChange={(e) => { setUsername(e.target.value); setResolved(null); }}
                    placeholder="@channel_name" className="flex-1 rounded-lg border border-border bg-surface px-4 py-2.5 text-text-primary outline-none focus:border-brand-500" />
                  <button onClick={handleResolve} disabled={resolving || !username.trim()} className="rounded-lg bg-surface-hover px-4 py-2.5 text-sm text-text-primary hover:bg-brand-500/20 disabled:opacity-50">
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
                  <input type="text" value={providerName} onChange={(e) => setProviderName(e.target.value)} placeholder={resolved?.title || username}
                    className="w-full rounded-lg border border-border bg-surface px-4 py-2.5 text-text-primary outline-none focus:border-brand-500" />
                  <button onClick={handleSubscribe} disabled={subscribing} className="mt-3 rounded-lg bg-brand-600 px-6 py-2.5 font-medium text-white hover:bg-brand-700 disabled:opacity-50">
                    {subscribing ? "..." : (isRu ? "Подключить канал" : "Connect Channel")}
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Connected Sources */}
          {providers.length === 0 ? (
            <div className="rounded-xl border border-border bg-surface-card p-8 text-center">
              <p className="text-text-secondary">{isRu ? "Нет подключённых источников" : "No connected sources"}</p>
              <p className="mt-1 text-sm text-text-muted">{isRu ? "Нажмите «+ Добавить» чтобы подключить Telegram-канал с сигналами." : "Click '+ Add' to connect a Telegram signal channel."}</p>
            </div>
          ) : (
            <div className="space-y-2">
              {providers.map((p) => (
                <div key={p.id} className="flex items-center justify-between rounded-xl border border-border bg-surface-card p-4">
                  <div>
                    <h3 className="font-semibold text-text-primary">{p.name}</h3>
                    <p className="text-xs text-text-muted">{p.description} | {p.total_signals} {isRu ? "сигналов" : "signals"}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`rounded px-2 py-0.5 text-xs font-bold ${p.is_active ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
                      {p.is_active ? (isRu ? "Активен" : "Active") : (isRu ? "Отключён" : "Off")}
                    </span>
                    {p.is_active && (
                      <button onClick={async () => { try { await api.unsubscribeTelegram(p.id); load(); } catch {} }}
                        className="text-sm text-red-400 hover:text-red-300">{isRu ? "Отключить" : "Disconnect"}</button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          <p className="mt-3 text-xs text-text-muted">
            {isRu
              ? "Требуется настройка TELEGRAM_API_ID и TELEGRAM_API_HASH в .env для работы парсера. Сигналы из подключённых каналов проходят AI-оценку и появляются в общей ленте."
              : "Requires TELEGRAM_API_ID and TELEGRAM_API_HASH in .env for the parser. Signals from connected channels are AI-rated and appear in the main feed."}
          </p>
        </div>
      )}
    </div>
  );
}

function ChannelCard({ name, platform, type, typeColor, desc, link, buttonText, isPremium }: {
  name: string; platform: string; type: string; typeColor: string; desc: string; link?: string; buttonText?: string; isPremium?: boolean;
}) {
  return (
    <div className={`rounded-xl border bg-surface-card p-4 ${isPremium ? "border-brand-500/50" : "border-border"}`}>
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs font-bold text-text-muted">{platform}</span>
        <span className={`rounded px-1.5 py-0.5 text-xs font-bold ${typeColor}`}>{type}</span>
      </div>
      <p className="font-semibold text-text-primary text-sm">{name}</p>
      <p className="mt-1 text-xs text-text-muted">{desc}</p>
      {link && buttonText && (
        <a href={link} target="_blank" rel="noopener"
          className={`mt-3 block w-full rounded-lg py-2 text-center text-xs font-medium ${isPremium ? "bg-brand-600 text-white hover:bg-brand-700" : "border border-border text-text-primary hover:bg-surface-hover"}`}>
          {buttonText}
        </a>
      )}
    </div>
  );
}
