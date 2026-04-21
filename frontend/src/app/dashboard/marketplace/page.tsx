"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { StrategyCard } from "@/components/strategy-card";
import type { StrategyResponse } from "@/types";

export default function MarketplacePage() {
  const [strategies, setStrategies] = useState<StrategyResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [priceFilter, setPriceFilter] = useState("");
  const [sortBy, setSortBy] = useState("ai_score");
  const [tagsFilter, setTagsFilter] = useState("");
  const { t } = useI18n();

  const load = useCallback(async () => {
    try {
      const data = await api.browseStrategies({ price_type: priceFilter || undefined, sort_by: sortBy, tags: tagsFilter || undefined });
      setStrategies(data.items);
      setTotal(data.total);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, [priceFilter, sortBy, tagsFilter]);

  useEffect(() => { load(); }, [load]);

  const PRICE_FILTERS = [
    { value: "", label: t("signals.all") },
    { value: "free", label: t("marketplace.free") },
    { value: "premium", label: t("marketplace.premium") },
    { value: "paid", label: t("marketplace.paid") },
  ];
  const SORT_OPTIONS = [
    { value: "ai_score", label: t("marketplace.sortScore") },
    { value: "subscriber_count", label: t("marketplace.sortPopular") },
    { value: "created_at", label: t("marketplace.sortNew") },
  ];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">{t("marketplace.title")}</h1>
        <p className="text-sm text-gray-400">{total} {t("marketplace.available")}</p>
      </div>
      <div className="mb-4 flex flex-wrap gap-3">
        <input type="text" placeholder={t("marketplace.filterTags")} value={tagsFilter} onChange={(e) => setTagsFilter(e.target.value)} className="rounded-lg border border-gray-700 bg-surface px-3 py-2 text-sm text-white outline-none focus:border-brand-500" />
        <div className="flex gap-1">
          {PRICE_FILTERS.map((f) => (
            <button key={f.value} onClick={() => setPriceFilter(f.value)} className={`rounded-lg px-3 py-2 text-sm transition ${priceFilter === f.value ? "bg-brand-500/20 text-brand-500" : "text-gray-400 hover:bg-surface-hover hover:text-white"}`}>{f.label}</button>
          ))}
        </div>
        <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="rounded-lg border border-gray-700 bg-surface px-3 py-2 text-sm text-white">
          {SORT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{t("common.sort")}: {o.label}</option>)}
        </select>
      </div>
      {loading ? (
        <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>
      ) : strategies.length === 0 ? (
        <div className="rounded-xl border border-gray-800 bg-surface-card p-12 text-center">
          <p className="text-gray-400">{t("marketplace.empty")}</p>
          <p className="mt-1 text-sm text-gray-500">{t("marketplace.emptyHint")}</p>
        </div>
      ) : (
        <div className="space-y-3">{strategies.map((s) => <StrategyCard key={s.id} strategy={s} />)}</div>
      )}
    </div>
  );
}
