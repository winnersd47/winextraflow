"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Provider } from "@/types";

export default function TelegramPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const { t } = useI18n();

  // Form state
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
    } catch (err) { console.error(err); }
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
      setError(err.message || "Could not resolve channel");
    } finally {
      setResolving(false);
    }
  };

  const handleSubscribe = async () => {
    setSubscribing(true);
    setError("");
    try {
      // Create provider
      const provider = await api.createProvider({
        name: providerName || username,
        source: "telegram",
        description: `Telegram: ${resolved?.title || username}`,
      });

      // Subscribe to channel
      if (resolved) {
        await api.subscribeTelegram(provider.id, {
          channel_id: resolved.id,
          channel_name: resolved.title,
        });
      } else {
        await api.subscribeTelegram(provider.id, {
          channel_username: username,
        });
      }

      // Reset form
      setShowForm(false);
      setUsername("");
      setResolved(null);
      setProviderName("");
      load();
    } catch (err: any) {
      setError(err.message || "Failed to subscribe");
    } finally {
      setSubscribing(false);
    }
  };

  const handleDisconnect = async (providerId: string) => {
    try {
      await api.unsubscribeTelegram(providerId);
      load();
    } catch (err: any) {
      console.error(err);
    }
  };

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">{t("telegram.title")}</h1>
          <p className="text-sm text-text-secondary">{t("telegram.subtitle")}</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
          {showForm ? t("telegram.cancel") : t("telegram.addChannel")}
        </button>
      </div>

      {/* Add Channel Form */}
      {showForm && (
        <div className="mb-6 rounded-xl border border-border bg-surface-card p-6 space-y-4">
          {error && <div className="rounded-lg bg-red-500/10 p-3 text-sm text-red-400">{error}</div>}

          {/* Step 1: Find channel */}
          <div>
            <label className="mb-1 block text-sm text-text-secondary">{t("telegram.username")}</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={username}
                onChange={(e) => { setUsername(e.target.value); setResolved(null); }}
                placeholder="@channel_name"
                className="flex-1 rounded-lg border border-border bg-surface px-4 py-2.5 text-text-primary outline-none focus:border-brand-500"
              />
              <button onClick={handleResolve} disabled={resolving || !username.trim()} className="rounded-lg bg-surface-hover px-4 py-2.5 text-sm font-medium text-text-primary transition hover:bg-brand-500/20 disabled:opacity-50">
                {resolving ? t("telegram.resolving") : t("telegram.resolve")}
              </button>
            </div>
          </div>

          {/* Step 2: Resolved channel info */}
          {resolved && (
            <div className="rounded-lg bg-green-500/10 border border-green-500/30 p-4">
              <p className="text-sm font-medium text-green-400">{t("telegram.channelFound")}</p>
              <p className="text-text-primary font-semibold">{resolved.title}</p>
              <p className="text-xs text-text-muted">ID: {resolved.id}</p>
            </div>
          )}

          {/* Step 3: Provider name + subscribe */}
          {(resolved || username.trim()) && (
            <div>
              <label className="mb-1 block text-sm text-text-secondary">{t("telegram.channelName")}</label>
              <input
                type="text"
                value={providerName}
                onChange={(e) => setProviderName(e.target.value)}
                placeholder={resolved?.title || username}
                className="w-full rounded-lg border border-border bg-surface px-4 py-2.5 text-text-primary outline-none focus:border-brand-500"
              />
              <button onClick={handleSubscribe} disabled={subscribing} className="mt-3 rounded-lg bg-brand-600 px-6 py-2.5 font-medium text-white transition hover:bg-brand-700 disabled:opacity-50">
                {subscribing ? "..." : t("telegram.subscribe")}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Channel List */}
      {providers.length === 0 ? (
        <div className="rounded-xl border border-border bg-surface-card p-12 text-center">
          <p className="text-2xl mb-2">✈️</p>
          <p className="text-text-secondary">{t("telegram.noChannels")}</p>
          <p className="mt-1 text-sm text-text-muted">{t("telegram.noChannelsHint")}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {providers.map((p) => (
            <div key={p.id} className="flex items-center justify-between rounded-xl border border-border bg-surface-card p-4">
              <div className="flex items-center gap-3">
                <span className="text-2xl">✈️</span>
                <div>
                  <h3 className="font-semibold text-text-primary">{p.name}</h3>
                  <p className="text-xs text-text-muted">{p.description}</p>
                  <p className="text-xs text-text-muted">{p.total_signals} {t("providers.signals")}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`rounded px-2 py-0.5 text-xs font-bold ${p.is_active ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
                  {p.is_active ? t("telegram.connected") : t("telegram.disconnected")}
                </span>
                {p.is_active && (
                  <button onClick={() => handleDisconnect(p.id)} className="text-sm text-red-400 hover:text-red-300">
                    {t("telegram.disconnect")}
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
