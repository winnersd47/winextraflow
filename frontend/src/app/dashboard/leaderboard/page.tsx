"use client";

import { useEffect, useState, useMemo } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { ProviderCard } from "@/components/provider-card";
import type { Provider } from "@/types";

const PAGE_SIZE = 10;

export default function LeaderboardPage() {
  const [allProviders, setAllProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const { t, locale } = useI18n();
  const isRu = locale === "ru";

  useEffect(() => {
    async function load() {
      try { setAllProviders((await api.getLeaderboard(100)).items); } catch {} finally { setLoading(false); }
    }
    load();
  }, []);

  const filtered = useMemo(() => {
    if (!search.trim()) return allProviders;
    const q = search.toLowerCase();
    return allProviders.filter(p => p.name.toLowerCase().includes(q));
  }, [allProviders, search]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  // Reset page when search changes
  useEffect(() => { setPage(0); }, [search]);

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-text-primary">{t("providers.leaderboard")}</h1>
        <p className="text-sm text-text-secondary">{t("providers.subtitle")}</p>
      </div>

      {/* Search */}
      <div className="mb-4">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={isRu ? "Поиск по названию провайдера..." : "Search by provider name..."}
          className="w-full rounded-lg border border-border bg-surface px-4 py-2.5 text-sm text-text-primary outline-none focus:border-brand-500"
        />
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
      ) : paged.length === 0 ? (
        <div className="rounded-xl border border-border bg-surface-card p-12 text-center">
          <p className="text-text-secondary">{search ? (isRu ? "Ничего не найдено" : "No results") : t("providers.empty")}</p>
          {!search && <p className="mt-1 text-sm text-text-muted">{t("providers.emptyHint")}</p>}
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {paged.map((p, i) => <ProviderCard key={p.id} provider={p} rank={page * PAGE_SIZE + i + 1} />)}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-xs text-text-muted">
                {isRu
                  ? `${page * PAGE_SIZE + 1}–${Math.min((page + 1) * PAGE_SIZE, filtered.length)} из ${filtered.length}`
                  : `${page * PAGE_SIZE + 1}–${Math.min((page + 1) * PAGE_SIZE, filtered.length)} of ${filtered.length}`}
              </p>
              <div className="flex gap-1">
                {Array.from({ length: totalPages }, (_, i) => (
                  <button
                    key={i}
                    onClick={() => setPage(i)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                      i === page ? "bg-brand-500 text-white" : "bg-surface-hover text-text-secondary hover:text-text-primary"
                    }`}
                  >
                    {i + 1}
                  </button>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
