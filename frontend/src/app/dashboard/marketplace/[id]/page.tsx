"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { formatConfidence, confidenceColor } from "@/lib/utils";
import type { StrategyResponse } from "@/types";

export default function StrategyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [strategy, setStrategy] = useState<StrategyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [subscribing, setSubscribing] = useState(false);
  const [subscribed, setSubscribed] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const s = await api.getStrategy(id);
        setStrategy(s);
        // Check if already subscribed
        const subs = await api.getMySubscriptions();
        setSubscribed(subs.some((sub) => sub.strategy_id === id && sub.status === "active"));
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  const handleSubscribe = async () => {
    setSubscribing(true);
    try {
      if (subscribed) {
        await api.unsubscribeStrategy(id);
        setSubscribed(false);
        if (strategy) strategy.subscriber_count--;
      } else {
        await api.subscribeStrategy(id);
        setSubscribed(true);
        if (strategy) strategy.subscriber_count++;
      }
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSubscribing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
      </div>
    );
  }

  if (!strategy) {
    return <div className="py-20 text-center text-gray-400">Strategy not found</div>;
  }

  const tags = strategy.tags?.split(",").map((t) => t.trim()).filter(Boolean) || [];

  return (
    <div className="mx-auto max-w-3xl">
      <button onClick={() => router.back()} className="mb-4 text-sm text-gray-400 hover:text-white">
        &larr; Back to Marketplace
      </button>

      <div className="rounded-xl border border-gray-800 bg-surface-card p-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">{strategy.name}</h1>
            <p className="mt-1 text-sm text-gray-500">
              {strategy.subscriber_count} subscribers
            </p>
          </div>
          <button
            onClick={handleSubscribe}
            disabled={subscribing}
            className={`rounded-lg px-6 py-2.5 text-sm font-medium transition ${
              subscribed
                ? "border border-gray-600 text-gray-400 hover:border-red-500 hover:text-red-400"
                : "bg-brand-600 text-white hover:bg-brand-700"
            } disabled:opacity-50`}
          >
            {subscribing ? "..." : subscribed ? "Unsubscribe" : "Subscribe"}
          </button>
        </div>

        {strategy.description && (
          <p className="mt-4 text-gray-300">{strategy.description}</p>
        )}

        {tags.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1">
            {tags.map((tag) => (
              <span key={tag} className="rounded bg-gray-700 px-2 py-0.5 text-xs text-gray-300">
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* Performance stats */}
        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-5">
          <MetricCard label="AI Score" value={formatConfidence(strategy.ai_score)} color={confidenceColor(strategy.ai_score)} />
          <MetricCard label="Win Rate" value={strategy.win_rate !== null ? `${(strategy.win_rate * 100).toFixed(0)}%` : "N/A"} />
          <MetricCard label="Sharpe" value={strategy.sharpe_ratio?.toFixed(2) ?? "N/A"} />
          <MetricCard label="Avg Profit" value={strategy.avg_profit !== null ? `${strategy.avg_profit.toFixed(2)}%` : "N/A"} />
          <MetricCard label="Total Signals" value={String(strategy.total_signals)} />
        </div>

        {/* Price */}
        <div className="mt-6 rounded-lg bg-surface p-4">
          <div className="flex items-center justify-between">
            <span className="text-gray-400">Pricing</span>
            <span className="text-lg font-bold text-white">
              {strategy.price_type === "free"
                ? "Free"
                : strategy.price_type === "premium"
                  ? "Premium Only"
                  : `$${strategy.price_monthly}/month`}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ label, value, color = "text-white" }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-lg bg-surface p-3 text-center">
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`mt-1 text-xl font-bold ${color}`}>{value}</p>
    </div>
  );
}
