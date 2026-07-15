"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatConfidence, confidenceColor } from "@/lib/utils";
import type { StrategyResponse } from "@/types";

export function generateStaticParams() { return []; }

export default function StrategyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { t } = useI18n();
  const [strategy, setStrategy] = useState<StrategyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [subscribing, setSubscribing] = useState(false);
  const [subscribed, setSubscribed] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const s = await api.getStrategy(id);
        setStrategy(s);
        const subs = await api.getMySubscriptions();
        setSubscribed(subs.some((sub) => sub.strategy_id === id && sub.status === "active"));
      } catch (err) { console.error(err); }
      finally { setLoading(false); }
    }
    load();
  }, [id]);

  const handleSubscribe = async () => {
    setSubscribing(true);
    try {
      if (subscribed) { await api.unsubscribeStrategy(id); setSubscribed(false); if (strategy) strategy.subscriber_count--; }
      else { await api.subscribeStrategy(id); setSubscribed(true); if (strategy) strategy.subscriber_count++; }
    } catch (err: any) { alert(err.message); }
    finally { setSubscribing(false); }
  };

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;
  if (!strategy) return <div className="py-20 text-center text-text-secondary">{t("marketplace.empty")}</div>;

  const tags = strategy.tags?.split(",").map((t) => t.trim()).filter(Boolean) || [];

  return (
    <div className="mx-auto max-w-3xl">
      <button onClick={() => router.back()} className="mb-4 text-sm text-text-secondary hover:text-text-primary">&larr; {t("marketplace.backTo")}</button>

      <div className="rounded-xl border border-border bg-surface-card p-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold text-text-primary">{strategy.name}</h1>
            <p className="mt-1 text-sm text-text-muted">{strategy.subscriber_count} {t("marketplace.subscribers").toLowerCase()}</p>
          </div>
          <button onClick={handleSubscribe} disabled={subscribing} className={`rounded-lg px-6 py-2.5 text-sm font-medium transition ${subscribed ? "border border-border text-text-secondary hover:border-red-500 hover:text-red-400" : "bg-brand-600 text-white hover:bg-brand-700"} disabled:opacity-50`}>
            {subscribing ? "..." : subscribed ? t("marketplace.unsubscribe") : t("marketplace.subscribe")}
          </button>
        </div>

        {strategy.description && <p className="mt-4 text-text-secondary">{strategy.description}</p>}
        {tags.length > 0 && <div className="mt-3 flex flex-wrap gap-1">{tags.map((tag) => <span key={tag} className="rounded bg-surface-hover px-2 py-0.5 text-xs text-text-secondary">{tag}</span>)}</div>}

        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-5">
          <MC label={t("providers.aiScore")} value={formatConfidence(strategy.ai_score)} color={confidenceColor(strategy.ai_score)} />
          <MC label={t("providers.winRate")} value={strategy.win_rate !== null ? `${(strategy.win_rate * 100).toFixed(0)}%` : "N/A"} />
          <MC label={t("providers.sharpe")} value={strategy.sharpe_ratio?.toFixed(2) ?? "N/A"} />
          <MC label="Avg Profit" value={strategy.avg_profit !== null ? `${strategy.avg_profit.toFixed(2)}%` : "N/A"} />
          <MC label={t("providers.signals")} value={String(strategy.total_signals)} />
        </div>

        <div className="mt-6 rounded-lg bg-surface p-4">
          <div className="flex items-center justify-between">
            <span className="text-text-secondary">{t("marketplace.pricing")}</span>
            <span className="text-lg font-bold text-text-primary">
              {strategy.price_type === "free" ? t("marketplace.priceFree") : strategy.price_type === "premium" ? t("marketplace.pricePremium") : `$${strategy.price_monthly}/mo`}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function MC({ label, value, color = "text-text-primary" }: { label: string; value: string; color?: string }) {
  return <div className="rounded-lg bg-surface p-3 text-center"><p className="text-xs text-text-muted">{label}</p><p className={`mt-1 text-xl font-bold ${color}`}>{value}</p></div>;
}
