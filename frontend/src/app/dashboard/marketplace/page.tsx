"use client";

import { useEffect, useState, useMemo } from "react";
import dynamic from "next/dynamic";
import { useI18n } from "@/lib/i18n";
import { useAuth } from "@/lib/auth";

const LeaderboardPage = dynamic(() => import("@/app/dashboard/leaderboard/page"), { ssr: false });

const PAGE_SIZE = 10;
const RISK_COLORS: Record<string, string> = { low: "text-green-400 bg-green-500/10", medium: "text-yellow-400 bg-yellow-500/10", high: "text-red-400 bg-red-500/10" };
const SOURCE_COLORS: Record<string, string> = { provider: "bg-brand-500/20 text-brand-500", mt5: "bg-blue-500/20 text-blue-400", tradingview: "bg-purple-500/20 text-purple-400" };
const SOURCE_LABELS_RU: Record<string, string> = { provider: "Провайдер", mt5: "MT5", tradingview: "TradingView" };

type MktTab = "strategies" | "leaderboard";

export default function MarketplacePage() {
  const [mktTab, setMktTab] = useState<MktTab>("strategies");
  const { locale } = useI18n();
  const isRu = locale === "ru";

  return (
    <div>
      <div className="mb-4 flex gap-2">
        <button onClick={() => setMktTab("strategies")}
          className={`rounded-lg px-4 py-2 text-sm font-medium transition ${mktTab === "strategies" ? "bg-brand-500 text-white" : "text-text-secondary hover:bg-surface-hover"}`}>
          {isRu ? "Стратегии" : "Strategies"}
        </button>
        <button onClick={() => setMktTab("leaderboard")}
          className={`rounded-lg px-4 py-2 text-sm font-medium transition ${mktTab === "leaderboard" ? "bg-brand-500 text-white" : "text-text-secondary hover:bg-surface-hover"}`}>
          {isRu ? "Лидерборд" : "Leaderboard"}
        </button>
      </div>
      {mktTab === "strategies" ? <StrategiesContent /> : <LeaderboardPage />}
    </div>
  );
}

function StrategiesContent() {
  const [items, setItems] = useState<any[]>([]);
  const [notice, setNotice] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [priceFilter, setPriceFilter] = useState("all");
  // Default was "rating", which put MQL5 advisors first and buried every
  // platform strategy, since only advisors carry a rating.
  const [sort, setSort] = useState("signals");
  const [page, setPage] = useState(0);
  const [simulating, setSimulating] = useState<string | null>(null);
  const [simResult, setSimResult] = useState<string | null>(null);
  const { locale } = useI18n();
  const { user } = useAuth();
  const isRu = locale === "ru";
  const isAdmin = user?.role === "admin";

  useEffect(() => {
    const load = async () => {
      try {
        const token = localStorage.getItem("token");
        const resp = await fetch("/api/v1/strategies/unified-marketplace", { headers: { Authorization: `Bearer ${token}` } });
        if (resp.ok) { const d = await resp.json(); setItems(d.items || []); setNotice(d.notice_ru || ""); }
      } catch {}
      finally { setLoading(false); }
    };
    load();
  }, []);

  const filtered = useMemo(() => {
    let result = items;
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(i => i.name.toLowerCase().includes(q) || (i.tickers || []).join(" ").toLowerCase().includes(q) || (i.description || "").toLowerCase().includes(q));
    }
    if (sourceFilter !== "all") result = result.filter(i => i.source === sourceFilter);
    if (priceFilter === "free") result = result.filter(i => !i.price_usd || i.price_usd === 0);
    if (priceFilter === "paid") result = result.filter(i => i.price_usd && i.price_usd > 0);

    result.sort((a, b) => {
      // Only MQL5 advisors carry a rating; platform strategies have none, so these
      // two sorts keep unrated items in place instead of dumping them at the end.
      if (sort === "rating") {
        if (a.rating == null && b.rating == null) return 0;
        if (a.rating == null) return 1;
        if (b.rating == null) return -1;
        return b.rating - a.rating;
      }
      if (sort === "reviews") {
        if (a.reviews == null && b.reviews == null) return 0;
        if (a.reviews == null) return 1;
        if (b.reviews == null) return -1;
        return b.reviews - a.reviews;
      }
      if (sort === "signals") return (b.signals_count || 0) - (a.signals_count || 0);
      if (sort === "price_asc") return (a.price_usd || 0) - (b.price_usd || 0);
      if (sort === "price_desc") return (b.price_usd || 0) - (a.price_usd || 0);
      if (sort === "subscribers") return (b.subscriber_count || 0) - (a.subscriber_count || 0);
      return (b.signals_count || 0) - (a.signals_count || 0);
    });
    return result;
  }, [items, search, sourceFilter, priceFilter, sort]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  useEffect(() => { setPage(0); }, [search, sourceFilter, priceFilter, sort]);

  const handleSimulate = async (strategyId: string) => {
    setSimulating(strategyId);
    setSimResult(null);
    try {
      const token = localStorage.getItem("token");
      const resp = await fetch(`/api/v1/strategies/${strategyId}/simulate`, { method: "POST", headers: { Authorization: `Bearer ${token}` } });
      if (resp.ok) {
        const d = await resp.json();
        setSimResult(isRu ? `${d.signals.length} сигналов создано (симуляция)` : `${d.signals.length} signals created (simulation)`);
      } else {
        const e = await resp.json();
        setSimResult(e.detail || "Error");
      }
    } catch { setSimResult("Error"); }
    finally { setSimulating(null); }
  };

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;

  const sourceCounts = { all: items.length, provider: items.filter(i => i.source === "provider").length, mt5: items.filter(i => i.source === "mt5").length, tradingview: items.filter(i => i.source === "tradingview").length };

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-text-primary">{isRu ? "Маркетплейс стратегий" : "Strategy Marketplace"}</h1>
        <p className="text-sm text-text-secondary">{filtered.length} {isRu ? "стратегий" : "strategies"}</p>
      </div>

      {simResult && (
        <div className="mb-4 rounded-lg bg-orange-500/10 p-3 text-sm text-orange-400">{simResult}</div>
      )}

      {/* Where the numbers on these cards come from, and which are not measured. */}
      {notice && (
        <div className="mb-4 rounded-lg border border-border bg-surface p-3 text-xs text-text-secondary">
          {notice}
        </div>
      )}

      {/* Search */}
      <div className="mb-4">
        <input type="text" value={search} onChange={e => setSearch(e.target.value)}
          placeholder={isRu ? "Поиск по названию, тикеру, описанию..." : "Search by name, ticker, description..."}
          className="w-full rounded-lg border border-border bg-surface px-4 py-2.5 text-sm text-text-primary outline-none focus:border-brand-500" />
      </div>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex gap-1">
          {[
            { key: "all", label: isRu ? `Все (${sourceCounts.all})` : `All (${sourceCounts.all})` },
            { key: "provider", label: `${isRu ? "Провайдеры" : "Providers"} (${sourceCounts.provider})` },
            { key: "mt5", label: `MT5 (${sourceCounts.mt5})` },
            { key: "tradingview", label: `TV (${sourceCounts.tradingview})` },
          ].map(f => (
            <button key={f.key} onClick={() => setSourceFilter(f.key)}
              className={`rounded-lg px-3 py-2 text-xs font-medium transition ${sourceFilter === f.key ? "bg-brand-500 text-white" : "text-text-secondary hover:bg-surface-hover"}`}>
              {f.label}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          {[
            { key: "all", label: isRu ? "Все цены" : "All prices" },
            { key: "free", label: isRu ? "Бесплатные" : "Free" },
            { key: "paid", label: isRu ? "Платные" : "Paid" },
          ].map(f => (
            <button key={f.key} onClick={() => setPriceFilter(f.key)}
              className={`rounded-lg px-3 py-2 text-xs font-medium transition ${priceFilter === f.key ? "bg-brand-500 text-white" : "text-text-secondary hover:bg-surface-hover"}`}>
              {f.label}
            </button>
          ))}
        </div>
        <select value={sort} onChange={e => setSort(e.target.value)} className="rounded-lg border border-border bg-surface px-3 py-2 text-xs text-text-primary">
          <option value="signals">{isRu ? "По числу сигналов" : "By signal count"}</option>
          <option value="rating">{isRu ? "По рейтингу MQL5" : "By MQL5 rating"}</option>
          <option value="reviews">{isRu ? "По отзывам MQL5" : "By MQL5 reviews"}</option>
          <option value="subscribers">{isRu ? "По подписчикам" : "By subscribers"}</option>
          <option value="price_asc">{isRu ? "Дешёвые" : "Price: low"}</option>
          <option value="price_desc">{isRu ? "Дорогие" : "Price: high"}</option>
        </select>
      </div>

      {/* Cards */}
      <div className="space-y-3">
        {paged.map(item => (
          <div key={item.id} className="rounded-xl border border-border bg-surface-card p-4">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex flex-wrap items-center gap-2 mb-1">
                  <h3 className="font-bold text-text-primary">{item.name}</h3>
                  <span className={`rounded px-2 py-0.5 text-xs font-bold ${SOURCE_COLORS[item.source] || ""}`}>
                    {SOURCE_LABELS_RU[item.source] || item.source}
                  </span>
                  <span className="rounded bg-purple-500/10 px-2 py-0.5 text-xs text-purple-400">
                    {isRu ? item.strategy_type_ru : item.strategy_type_en}
                  </span>
                  <span className={`rounded px-2 py-0.5 text-xs ${RISK_COLORS[item.risk] || ""}`}>
                    {isRu ? `Риск: ${item.risk_ru}` : `Risk: ${item.risk}`}
                  </span>
                  {item.moex_compatible && <span className="rounded bg-blue-500/10 px-1.5 py-0.5 text-xs text-blue-400">MOEX</span>}
                  {/* Rating only where one exists (MQL5 snapshot), dated so it is
                      not read as current. Platform strategies have no reviews, so
                      they show a signal count instead of invented stars. */}
                  {item.rating != null && (
                    <span className="text-xs text-yellow-400" title={item.stats_as_of ? `MQL5, ${item.stats_as_of}` : undefined}>
                      {item.rating.toFixed(1)}/5
                      {item.stats_as_of && <span className="ml-1 text-text-muted">({item.stats_as_of})</span>}
                    </span>
                  )}
                  {item.reviews != null && (
                    <span className="text-xs text-text-muted">{item.reviews} {isRu ? "отзывов на MQL5" : "MQL5 reviews"}</span>
                  )}
                  {item.signals_count != null && item.signals_count > 0 && (
                    <span className="text-xs text-text-muted">{item.signals_count} {isRu ? "сигналов" : "signals"}</span>
                  )}
                  {item.is_demo && (
                    <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-xs text-amber-400"
                      title={item.demo_notice_ru || ""}>
                      {isRu ? "демо-данные" : "demo data"}
                    </span>
                  )}
                  {item.subscriber_count != null && item.subscriber_count > 0 && <span className="text-xs text-brand-500">{item.subscriber_count} {isRu ? "подп." : "subs"}</span>}
                </div>
                <p className="text-sm text-text-secondary line-clamp-2">{item.description}</p>
                {item.tickers?.length > 0 && (
                  <div className="mt-1 flex gap-1">{item.tickers.slice(0, 5).map((t: string) => <span key={t} className="rounded bg-surface-hover px-1.5 py-0.5 text-xs text-text-muted">{t}</span>)}</div>
                )}
                {/* Win Rate + Sharpe for providers */}
                {item.source === "provider" && item.win_rate != null && (
                  <div className="mt-2 flex gap-4 text-xs">
                    <span className={item.win_rate >= 0.65 ? "text-green-400" : "text-text-muted"}>WR: {(item.win_rate * 100).toFixed(0)}%</span>
                    {item.sharpe_ratio != null && <span className="text-text-muted">Sharpe: {item.sharpe_ratio.toFixed(1)}</span>}
                    {item.avg_profit != null && <span className={item.avg_profit >= 0 ? "text-green-400" : "text-red-400"}>Avg: {item.avg_profit >= 0 ? "+" : ""}{item.avg_profit.toFixed(1)}%</span>}
                  </div>
                )}
                {/* Webhook template for TradingView */}
                {item.webhook_template && (
                  <details className="mt-2"><summary className="cursor-pointer text-xs text-brand-500">Webhook</summary>
                    <div className="mt-1 rounded bg-surface p-2 font-mono text-xs text-text-muted break-all">{item.webhook_template}</div>
                  </details>
                )}
              </div>
              <div className="flex flex-col gap-2 flex-shrink-0 ml-4 items-end">
                {item.url ? (
                  <a href={item.url} target="_blank" rel="noopener" className="rounded-lg bg-brand-600 px-4 py-2 text-xs font-medium text-white hover:bg-brand-700">
                    {isRu ? "Открыть" : "Open"}
                  </a>
                ) : (
                  <a href={`/dashboard/marketplace/${item.id}`} className="rounded-lg bg-brand-600 px-4 py-2 text-xs font-medium text-white hover:bg-brand-700">
                    {isRu ? "Подробнее" : "Details"}
                  </a>
                )}
                <span className={`text-xs font-bold ${item.price_usd ? "text-yellow-400" : "text-green-400"}`}>
                  {item.price_usd ? (isRu ? `${Math.round(item.price_usd * 90).toLocaleString("ru-RU")} ₽` : `$${item.price_usd}`) : (isRu ? "Бесплатно" : "Free")}
                </span>
                {/* Simulate button for admin */}
                {isAdmin && item.can_simulate && (
                  <button onClick={() => handleSimulate(item.id)} disabled={simulating === item.id}
                    className="rounded bg-orange-500/10 px-3 py-1 text-xs text-orange-400 hover:bg-orange-500/20 disabled:opacity-50">
                    {simulating === item.id ? "..." : (isRu ? "Симуляция" : "Simulate")}
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-between">
          <p className="text-xs text-text-muted">
            {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, filtered.length)} {isRu ? "из" : "of"} {filtered.length}
          </p>
          <div className="flex gap-1">
            {Array.from({ length: Math.min(totalPages, 10) }, (_, i) => (
              <button key={i} onClick={() => setPage(i)}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${i === page ? "bg-brand-500 text-white" : "bg-surface-hover text-text-secondary"}`}>
                {i + 1}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Disclaimer */}
      <div className="mt-4 rounded-lg border border-yellow-500/20 bg-yellow-500/5 px-4 py-2">
        <p className="text-xs text-yellow-400/80">
          {isRu
            ? "Рейтинги и описания стратегий носят информационный характер. Прошлые результаты НЕ гарантируют будущую доходность. Не является инвестиционной рекомендацией."
            : "Strategy ratings and descriptions are for informational purposes. Past performance does NOT guarantee future returns. Not investment advice."}
        </p>
      </div>
    </div>
  );
}
