"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { StrategyCard } from "@/components/strategy-card";
import type { Provider, StrategyResponse } from "@/types";

export default function MarketplacePage() {
  const [strategies, setStrategies] = useState<StrategyResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [priceFilter, setPriceFilter] = useState("");
  const [sortBy, setSortBy] = useState("ai_score");
  const [tagsFilter, setTagsFilter] = useState("");

  // Publish form
  const [showPublish, setShowPublish] = useState(false);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [pubProviderId, setPubProviderId] = useState("");
  const [pubName, setPubName] = useState("");
  const [pubDesc, setPubDesc] = useState("");
  const [pubTags, setPubTags] = useState("");
  const [pubPrice, setPubPrice] = useState("free");
  const [pubMonthly, setPubMonthly] = useState("0");
  const [publishing, setPublishing] = useState(false);
  const [pubError, setPubError] = useState("");
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
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">{t("marketplace.title")}</h1>
          <p className="text-sm text-text-secondary">{total} {t("marketplace.available")}</p>
        </div>
        <button onClick={async () => {
          if (!showPublish) { try { setProviders((await api.getProviders()).items); } catch {} }
          setShowPublish(!showPublish);
        }} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
          {showPublish ? t("telegram.cancel") : t("marketplace.publish")}
        </button>
      </div>

      {/* Publish Strategy Form */}
      {showPublish && (
        <div className="mb-6 rounded-xl border border-border bg-surface-card p-6 space-y-3">
          {pubError && <div className="rounded-lg bg-red-500/10 p-3 text-sm text-red-400">{pubError}</div>}
          <div>
            <label className="mb-1 block text-sm text-text-secondary">{t("createSignal.provider")}</label>
            <select value={pubProviderId} onChange={(e) => setPubProviderId(e.target.value)} className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-text-primary">
              <option value="">—</option>
              {providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm text-text-secondary">{t("marketplace.strategyName")}</label>
            <input type="text" value={pubName} onChange={(e) => setPubName(e.target.value)} placeholder="Alpha BTC Scalper" className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-text-primary outline-none focus:border-brand-500" />
          </div>
          <div>
            <label className="mb-1 block text-sm text-text-secondary">{t("marketplace.description")}</label>
            <textarea value={pubDesc} onChange={(e) => setPubDesc(e.target.value)} rows={2} className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-text-primary outline-none focus:border-brand-500" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm text-text-secondary">{t("marketplace.tags")}</label>
              <input type="text" value={pubTags} onChange={(e) => setPubTags(e.target.value)} placeholder="crypto,btc,scalping" className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-text-primary outline-none focus:border-brand-500" />
            </div>
            <div>
              <label className="mb-1 block text-sm text-text-secondary">{t("marketplace.pricing")}</label>
              <select value={pubPrice} onChange={(e) => setPubPrice(e.target.value)} className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-text-primary">
                <option value="free">{t("marketplace.free")}</option>
                <option value="premium">{t("marketplace.premium")}</option>
                <option value="paid">{t("marketplace.paid")}</option>
              </select>
            </div>
          </div>
          {pubPrice === "paid" && (
            <div>
              <label className="mb-1 block text-sm text-text-secondary">$/month</label>
              <input type="number" value={pubMonthly} onChange={(e) => setPubMonthly(e.target.value)} className="w-32 rounded-lg border border-border bg-surface px-3 py-2.5 text-text-primary" />
            </div>
          )}
          <button onClick={async () => {
            if (!pubProviderId || !pubName) { setPubError("Provider and name required"); return; }
            setPublishing(true); setPubError("");
            try {
              const token = localStorage.getItem("token");
              const res = await fetch("/api/v1/strategies", {
                method: "POST",
                headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                body: JSON.stringify({
                  provider_id: pubProviderId, name: pubName, description: pubDesc,
                  tags: pubTags, price_type: pubPrice, price_monthly: parseFloat(pubMonthly) || 0,
                }),
              });
              if (res.ok) { setShowPublish(false); load(); }
              else { const d = await res.json(); setPubError(d.detail || "Failed"); }
            } catch { setPubError("Network error"); }
            finally { setPublishing(false); }
          }} disabled={publishing} className="rounded-lg bg-brand-600 px-6 py-2.5 font-medium text-white hover:bg-brand-700 disabled:opacity-50">
            {publishing ? "..." : t("marketplace.publishButton")}
          </button>
        </div>
      )}
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
