"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ProviderCard } from "@/components/provider-card";
import type { Provider } from "@/types";

export default function LeaderboardPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await api.getLeaderboard(20);
        setProviders(data.items);
      } catch (err) {
        console.error("Failed to load leaderboard:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Provider Leaderboard</h1>
        <p className="text-sm text-gray-400">
          Top signal providers ranked by AI composite score
        </p>
      </div>

      {loading ? (
        <div className="flex justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
        </div>
      ) : providers.length === 0 ? (
        <div className="rounded-xl border border-gray-800 bg-surface-card p-12 text-center">
          <p className="text-gray-400">No rated providers yet</p>
          <p className="mt-1 text-sm text-gray-500">
            Providers appear here after they have closed signals with an AI score
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {providers.map((provider, i) => (
            <ProviderCard key={provider.id} provider={provider} rank={i + 1} />
          ))}
        </div>
      )}
    </div>
  );
}
