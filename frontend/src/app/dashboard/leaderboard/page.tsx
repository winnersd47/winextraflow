"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { ProviderCard } from "@/components/provider-card";
import type { Provider } from "@/types";

export default function LeaderboardPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const { t, locale } = useI18n();
  const isRu = locale === "ru";

  useEffect(() => {
    async function load() {
      try { setProviders((await api.getLeaderboard(20)).items); } catch (err) { console.error(err); } finally { setLoading(false); }
    }
    load();
  }, []);

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-text-primary">{t("providers.leaderboard")}</h1>
        <p className="text-sm text-text-secondary">{t("providers.subtitle")}</p>
      </div>

      {/* Disclaimer */}
      <div className="mb-6 rounded-lg border border-yellow-500/20 bg-yellow-500/5 px-4 py-2">
        <p className="text-xs text-yellow-400/80">
          {isRu
            ? "Рейтинг провайдеров основан на исторических данных и AI-анализе. Прошлые результаты НЕ гарантируют будущую доходность. Рейтинг не является инвестиционной рекомендацией."
            : "Provider ratings are based on historical data and AI analysis. Past performance does NOT guarantee future returns. Ratings are not investment advice."}
        </p>
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>
      ) : providers.length === 0 ? (
        <div className="rounded-xl border border-border bg-surface-card p-12 text-center">
          <p className="text-text-secondary">{t("providers.empty")}</p>
          <p className="mt-1 text-sm text-text-muted">{t("providers.emptyHint")}</p>
        </div>
      ) : (
        <div className="space-y-3">{providers.map((p, i) => <ProviderCard key={p.id} provider={p} rank={i + 1} />)}</div>
      )}
    </div>
  );
}
