"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { StrategyCard } from "@/components/strategy-card";
import type { Provider, StrategyResponse } from "@/types";

export default function MarketplacePage() {
  const [tab, setTab] = useState<"strategies" | "advisors">("strategies");
  const [strategies, setStrategies] = useState<StrategyResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [priceFilter, setPriceFilter] = useState("");
  const [sortBy, setSortBy] = useState("ai_score");
  const [tagsFilter, setTagsFilter] = useState("");
  const [advisors, setAdvisors] = useState<any[]>([]);
  const [advisorsLoading, setAdvisorsLoading] = useState(false);
  const [eaSearch, setEaSearch] = useState("");
  const [eaFilter, setEaFilter] = useState("all");
  const [eaSort, setEaSort] = useState("reviews");
  const [eaPage, setEaPage] = useState(0);
  // locale from t below

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
  const { t, locale } = useI18n();
  const isRu = locale === "ru";

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

  const [hasMt5Account, setHasMt5Account] = useState(false);

  // Load advisors + check MT5 connection on tab switch
  useEffect(() => {
    if (tab === "advisors" && advisors.length === 0) {
      setAdvisorsLoading(true);
      const token = localStorage.getItem("token");
      const h = { Authorization: `Bearer ${token}` };
      Promise.all([
        fetch("/api/v1/advisors", { headers: h }).then(r => r.json()),
        fetch("/api/v1/execution/accounts", { headers: h }).then(r => r.ok ? r.json() : []).catch(() => []),
      ]).then(([advData, accounts]) => {
        setAdvisors(advData.advisors || []);
        const mt5 = (accounts || []).some((a: any) => a.exchange === "metatrader5" && a.is_active);
        setHasMt5Account(mt5);
      }).catch(() => {})
        .finally(() => setAdvisorsLoading(false));
    }
  }, [tab]);

  const RISK_COLORS: Record<string, string> = { low: "text-green-400 bg-green-500/10", medium: "text-yellow-400 bg-yellow-500/10", high: "text-red-400 bg-red-500/10" };

  // Advisor filtering + pagination
  const EA_PAGE_SIZE = 8;
  const filteredAdvisors = advisors.filter(ea => {
    // Search
    if (eaSearch) {
      const q = eaSearch.toLowerCase();
      if (!ea.name.toLowerCase().includes(q) && !ea.author?.toLowerCase().includes(q) && !(ea.tickers || []).join(" ").toLowerCase().includes(q)) return false;
    }
    // Filter
    if (eaFilter === "free" && ea.price_usd) return false;
    if (eaFilter === "paid" && !ea.price_usd) return false;
    return true;
  }).sort((a: any, b: any) => {
    if (eaSort === "rating") return (b.rating || 0) - (a.rating || 0);
    if (eaSort === "reviews") return (b.reviews || 0) - (a.reviews || 0);
    if (eaSort === "price_asc") return (a.price_usd || 0) - (b.price_usd || 0);
    if (eaSort === "price_desc") return (b.price_usd || 0) - (a.price_usd || 0);
    return (b.reviews || 0) - (a.reviews || 0);
  });
  const eaTotalPages = Math.ceil(filteredAdvisors.length / EA_PAGE_SIZE);
  const filteredAdvisorsPage = filteredAdvisors.slice(eaPage * EA_PAGE_SIZE, (eaPage + 1) * EA_PAGE_SIZE);

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">{t("marketplace.title")}</h1>
          <p className="text-sm text-text-secondary">{tab === "strategies" ? `${total} ${t("marketplace.available")}` : `${advisors.length} ${isRu ? "советников" : "advisors"}`}</p>
        </div>
        <button onClick={async () => {
          if (!showPublish) { try { setProviders((await api.getProviders()).items); } catch {} }
          setShowPublish(!showPublish);
        }} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
          {showPublish ? t("telegram.cancel") : t("marketplace.publish")}
        </button>
      </div>

      {/* Tabs: Strategies / Advisors */}
      <div className="mb-6 flex gap-1 rounded-xl border border-border bg-surface-card p-1">
        <button onClick={() => setTab("strategies")} className={`flex-1 rounded-lg px-4 py-2 text-sm font-medium transition ${tab === "strategies" ? "bg-brand-500 text-white" : "text-text-secondary hover:bg-surface-hover"}`}>
          {isRu ? "Стратегии провайдеров" : "Provider Strategies"}
        </button>
        <button onClick={() => setTab("advisors")} className={`flex-1 rounded-lg px-4 py-2 text-sm font-medium transition ${tab === "advisors" ? "bg-brand-500 text-white" : "text-text-secondary hover:bg-surface-hover"}`}>
          {isRu ? "Советники MT5" : "MT5 Advisors"} ({advisors.length || "..."})
        </button>
      </div>

      {/* ═══ TAB: Strategies ═══ */}
      {tab === "strategies" && (<>

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
        <input type="text" placeholder={t("marketplace.filterTags")} value={tagsFilter} onChange={(e) => setTagsFilter(e.target.value)} className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-500" />
        <div className="flex gap-1">
          {PRICE_FILTERS.map((f) => (
            <button key={f.value} onClick={() => setPriceFilter(f.value)} className={`rounded-lg px-3 py-2 text-sm transition ${priceFilter === f.value ? "bg-brand-500/20 text-brand-500" : "text-text-secondary hover:bg-surface-hover hover:text-text-primary"}`}>{f.label}</button>
          ))}
        </div>
        <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary">
          {SORT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{t("common.sort")}: {o.label}</option>)}
        </select>
      </div>
      {loading ? (
        <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>
      ) : strategies.length === 0 ? (
        <div className="rounded-xl border border-border bg-surface-card p-12 text-center">
          <p className="text-text-secondary">{t("marketplace.empty")}</p>
          <p className="mt-1 text-sm text-text-muted">{t("marketplace.emptyHint")}</p>
        </div>
      ) : (
        <div className="space-y-3">{strategies.map((s) => <StrategyCard key={s.id} strategy={s} />)}</div>
      )}
      </>)}

      {/* ═══ TAB: MT5 Advisors ═══ */}
      {tab === "advisors" && (
        <div>
          <p className="mb-4 text-sm text-text-secondary">
            {isRu
              ? "Торговые советники (Expert Advisors) из MQL5 Market. Скачайте, установите в MetaTrader 5 и подключите счёт к платформе для синхронизации сигналов."
              : "Expert Advisors from MQL5 Market. Download, install in MetaTrader 5, and connect your account to sync signals."}
          </p>

          {/* Search */}
          <div className="mb-4">
            <input type="text" value={eaSearch} onChange={e => { setEaSearch(e.target.value); setEaPage(0); }}
              placeholder={isRu ? "Поиск по маркету..." : "Search advisors..."}
              className="w-full rounded-lg border border-border bg-surface px-4 py-2.5 text-sm text-text-primary outline-none focus:border-brand-500" />
          </div>

          {/* Filter tabs + sort */}
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <div className="flex gap-1">
              {[
                { key: "all", label: isRu ? "Все" : "All" },
                { key: "free", label: isRu ? "Бесплатные" : "Free" },
                { key: "paid", label: isRu ? "Платные" : "Paid" },
              ].map(f => (
                <button key={f.key} onClick={() => { setEaFilter(f.key); setEaPage(0); }}
                  className={`rounded-lg px-4 py-2 text-sm font-medium transition ${eaFilter === f.key ? "bg-brand-500 text-white" : "text-text-secondary hover:bg-surface-hover"}`}>
                  {f.label}
                </button>
              ))}
            </div>
            <select value={eaSort} onChange={e => { setEaSort(e.target.value); setEaPage(0); }}
              className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary">
              <option value="reviews">{isRu ? "По отзывам" : "By reviews"}</option>
              <option value="rating">{isRu ? "По рейтингу" : "By rating"}</option>
              <option value="price_asc">{isRu ? "Сначала дешёвые" : "Price: low first"}</option>
              <option value="price_desc">{isRu ? "Сначала дорогие" : "Price: high first"}</option>
            </select>
          </div>

          {advisorsLoading ? (
            <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>
          ) : (
            <div className="space-y-3">
              {filteredAdvisorsPage.map((ea: any) => (
                <div key={ea.id} className="rounded-xl border border-border bg-surface-card p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex flex-wrap items-center gap-2 mb-1">
                        <h3 className="font-bold text-text-primary">{ea.name}</h3>
                        <span className="rounded bg-purple-500/10 px-2 py-0.5 text-xs text-purple-400" title={isRu ? "Тип стратегии" : "Strategy type"}>
                          {isRu ? `Стратегия: ${ea.strategy_name_ru}` : `Strategy: ${ea.strategy_name_en}`}
                        </span>
                        <span className={`rounded px-2 py-0.5 text-xs ${RISK_COLORS[ea.risk] || ""}`} title={isRu ? "Уровень риска" : "Risk level"}>
                          {isRu ? `Риск: ${ea.risk_ru}` : `Risk: ${ea.risk}`}
                        </span>
                        <span className="text-xs text-yellow-400" title={isRu ? "Рейтинг на MQL5 Market" : "MQL5 Market rating"}>
                          {ea.rating}/5
                        </span>
                        <span className="text-xs text-text-muted" title={isRu ? "Количество отзывов" : "Number of reviews"}>
                          {ea.reviews} {isRu ? "отзывов" : "reviews"}
                        </span>
                      </div>
                      <p className="text-sm text-text-secondary">{isRu ? ea.description_ru : ea.description_en}</p>
                      <div className="mt-2 flex items-center gap-3 text-xs text-text-muted">
                        <span>{isRu ? "Автор" : "Author"}: {ea.author}</span>
                        <span>{isRu ? "Тикеры" : "Tickers"}: {ea.tickers?.join(", ")}</span>
                        <span>TF: {ea.timeframe}</span>
                      </div>
                    </div>
                    <div className="flex flex-col gap-2 flex-shrink-0 ml-4">
                      {hasMt5Account ? (
                        <>
                          <span className="rounded-lg bg-green-500/20 px-4 py-2 text-center text-xs font-bold text-green-400">
                            {isRu ? "Подключён" : "Connected"}
                          </span>
                          <a href={ea.mql5_url} target="_blank" rel="noopener" className="text-center text-xs text-brand-500 hover:underline">
                            {isRu ? "Страница MQL5" : "MQL5 Page"}
                          </a>
                        </>
                      ) : (
                        <a href={ea.mql5_url} target="_blank" rel="noopener"
                          className="rounded-lg bg-brand-600 px-4 py-2 text-center text-xs font-medium text-white hover:bg-brand-700">
                          {isRu ? "Скачать" : "Download"}
                        </a>
                      )}
                      <span className={`text-center text-xs font-bold ${ea.price_usd ? "text-yellow-400" : "text-green-400"}`}>
                        {ea.price_usd ? (isRu ? `${Math.round(ea.price_usd * 90).toLocaleString("ru-RU")} ₽` : `$${ea.price_usd}`) : (isRu ? "Бесплатно" : "Free")}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Pagination */}
          {eaTotalPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-xs text-text-muted">
                {isRu
                  ? `${eaPage * EA_PAGE_SIZE + 1}–${Math.min((eaPage + 1) * EA_PAGE_SIZE, filteredAdvisors.length)} из ${filteredAdvisors.length}`
                  : `${eaPage * EA_PAGE_SIZE + 1}–${Math.min((eaPage + 1) * EA_PAGE_SIZE, filteredAdvisors.length)} of ${filteredAdvisors.length}`}
              </p>
              <div className="flex gap-1">
                {Array.from({ length: Math.min(eaTotalPages, 8) }, (_, i) => {
                  // Show first pages, ..., last page
                  let pageNum = i;
                  if (eaTotalPages > 8 && i >= 6) pageNum = i === 6 ? -1 : eaTotalPages - 1; // -1 = ellipsis
                  if (pageNum === -1) return <span key="dots" className="px-2 py-1.5 text-xs text-text-muted">...</span>;
                  return (
                    <button key={pageNum} onClick={() => setEaPage(pageNum)}
                      className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${pageNum === eaPage ? "bg-brand-500 text-white" : "bg-surface-hover text-text-secondary hover:text-text-primary"}`}>
                      {pageNum + 1}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Connect MT5 */}
          <div className="mt-6 rounded-xl border border-brand-500/30 bg-brand-500/5 p-6">
            <h3 className="mb-2 font-bold text-text-primary">{isRu ? "Подключить MT5 счёт" : "Connect MT5 Account"}</h3>
            <p className="mb-4 text-sm text-text-secondary">
              {isRu
                ? "После установки советника подключите свой MT5 счёт через MetaApi для автоматической синхронизации сигналов и исполнения сделок на платформе."
                : "After installing an advisor, connect your MT5 account via MetaApi for automatic signal sync and trade execution on the platform."}
            </p>
            <ol className="mb-4 space-y-1 text-sm text-text-secondary">
              <li>1. {isRu ? "Скачайте советник из каталога выше" : "Download an advisor from the catalog above"}</li>
              <li>2. {isRu ? "Установите его в MetaTrader 5 на вашем VPS или компьютере" : "Install it in MetaTrader 5 on your VPS or computer"}</li>
              <li>3. {isRu ? "Зарегистрируйтесь на metaapi.cloud и получите токен" : "Register at metaapi.cloud and get a token"}</li>
              <li>4. {isRu ? "Перейдите в Исполнение → Добавить аккаунт → MetaTrader 5" : "Go to Execution → Add Account → MetaTrader 5"}</li>
            </ol>
            <a href="/dashboard/execution" className="inline-block rounded-lg bg-brand-600 px-6 py-2 text-sm font-medium text-white hover:bg-brand-700">
              {isRu ? "Перейти в Исполнение" : "Go to Execution"}
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
