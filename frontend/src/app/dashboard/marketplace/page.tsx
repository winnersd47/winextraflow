"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { StrategyCard } from "@/components/strategy-card";
import type { StrategyResponse } from "@/types";

const PRICE_FILTERS = [
  { value: "", label: "All" },
  { value: "free", label: "Free" },
  { value: "premium", label: "Premium" },
  { value: "paid", label: "Paid" },
];

const SORT_OPTIONS = [
  { value: "ai_score", label: "AI Score" },
  { value: "subscriber_count", label: "Popular" },
  { value: "created_at", label: "Newest" },
];

export default function MarketplacePage() {
  const [strategies, setStrategies] = useState<StrategyResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [priceFilter, setPriceFilter] = useState("");
  const [sortBy, setSortBy] = useState("ai_score");
  const [tagsFilter, setTagsFilter] = useState("");

  const fetch = useCallback(async () => {
    try {
      const data = await api.browseStrategies({
        price_type: priceFilter || undefined,
        sort_by: sortBy,
        tags: tagsFilter || undefined,
      });
      setStrategies(data.items);
      setTotal(data.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [priceFilter, sortBy, tagsFilter]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Strategy Marketplace</h1>
        <p className="text-sm text-gray-400">
          {total} strategies available
        </p>
      </div>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap gap-3">
        <input
          type="text"
          placeholder="Filter by tags..."
          value={tagsFilter}
          onChange={(e) => setTagsFilter(e.target.value)}
          className="rounded-lg border border-gray-700 bg-surface px-3 py-2 text-sm text-white outline-none focus:border-brand-500"
        />
        <div className="flex gap-1">
          {PRICE_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setPriceFilter(f.value)}
              className={`rounded-lg px-3 py-2 text-sm transition ${
                priceFilter === f.value
                  ? "bg-brand-500/20 text-brand-500"
                  : "text-gray-400 hover:bg-surface-hover hover:text-white"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="rounded-lg border border-gray-700 bg-surface px-3 py-2 text-sm text-white"
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              Sort: {o.label}
            </option>
          ))}
        </select>
      </div>

      {/* Strategy list */}
      {loading ? (
        <div className="flex justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
        </div>
      ) : strategies.length === 0 ? (
        <div className="rounded-xl border border-gray-800 bg-surface-card p-12 text-center">
          <p className="text-gray-400">No strategies found</p>
          <p className="mt-1 text-sm text-gray-500">
            Publish a strategy to see it here
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {strategies.map((s) => (
            <StrategyCard key={s.id} strategy={s} />
          ))}
        </div>
      )}
    </div>
  );
}
