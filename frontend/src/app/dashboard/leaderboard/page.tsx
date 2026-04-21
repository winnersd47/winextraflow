"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { ProviderCard } from "@/components/provider-card";
import type { Provider } from "@/types";

export default function LeaderboardPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const { t } = useI18n();

  useEffect(() => {
    async function load() {
      try { setProviders((await api.getLeaderboard(20)).items); } catch (err) { console.error(err); } finally { setLoading(false); }
    }
    load();
  }, []);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">{t("providers.leaderboard")}</h1>
        <p className="text-sm text-gray-400">{t("providers.subtitle")}</p>
      </div>
      {loading ? (
        <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>
      ) : providers.length === 0 ? (
        <div className="rounded-xl border border-gray-800 bg-surface-card p-12 text-center">
          <p className="text-gray-400">{t("providers.empty")}</p>
          <p className="mt-1 text-sm text-gray-500">{t("providers.emptyHint")}</p>
        </div>
      ) : (
        <div className="space-y-3">{providers.map((p, i) => <ProviderCard key={p.id} provider={p} rank={i + 1} />)}</div>
      )}
    </div>
  );
}
