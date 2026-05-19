import Link from "next/link";
import type { StrategyResponse } from "@/types";
import { useI18n } from "@/lib/i18n";

function calcRisk(wr: number | null, sharpe: number | null, dd: number | null): { level: string; ru: string; en: string; color: string } {
  // Risk from win rate + sharpe
  const wrScore = wr ? (wr >= 0.7 ? 2 : wr >= 0.55 ? 1 : 0) : 0;
  const shScore = sharpe ? (sharpe >= 8 ? 2 : sharpe >= 4 ? 1 : 0) : 0;
  const total = wrScore + shScore;
  if (total >= 3) return { level: "low", ru: "Низкий", en: "Low", color: "text-green-400 bg-green-500/10" };
  if (total >= 1) return { level: "medium", ru: "Средний", en: "Medium", color: "text-yellow-400 bg-yellow-500/10" };
  return { level: "high", ru: "Высокий", en: "High", color: "text-red-400 bg-red-500/10" };
}

function classifyStrategy(tags: string | null, wr: number | null): { ru: string; en: string } {
  const t = (tags || "").toLowerCase();
  if (t.includes("scalp")) return { ru: "Скальпинг", en: "Scalping" };
  if (t.includes("breakout")) return { ru: "Пробой", en: "Breakout" };
  if (t.includes("trend") || t.includes("momentum")) return { ru: "Тренд", en: "Trend Following" };
  if (t.includes("defi") || t.includes("research")) return { ru: "Аналитика", en: "Analytics" };
  if (t.includes("value")) return { ru: "Стоимостная", en: "Value" };
  if (t.includes("ai")) return { ru: "ML/AI", en: "ML/AI" };
  if (t.includes("altcoin") || t.includes("crypto")) return { ru: "Крипто", en: "Crypto" };
  if (t.includes("forex")) return { ru: "Форекс", en: "Forex" };
  if (t.includes("indices") || t.includes("index")) return { ru: "Индексы", en: "Indices" };
  return { ru: "Мульти", en: "Multi" };
}

export function StrategyCard({ strategy }: { strategy: StrategyResponse }) {
  const { t, locale } = useI18n();
  const isRu = locale === "ru";
  const tags = strategy.tags?.split(",").map((t) => t.trim()).filter(Boolean) || [];
  const risk = calcRisk(strategy.win_rate, strategy.sharpe_ratio, null);
  const stratType = classifyStrategy(strategy.tags, strategy.win_rate);

  return (
    <Link href={`/dashboard/marketplace/${strategy.id}`} className="block rounded-xl border border-border bg-surface-card p-5 transition hover:border-brand-500/30 hover:bg-surface-hover">
      {/* Header: name + badges */}
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <h3 className="text-lg font-bold text-text-primary">{strategy.name.replace("[TEST] ", "")}</h3>
            <span className="rounded bg-purple-500/10 px-2 py-0.5 text-xs text-purple-400" title={isRu ? "Тип стратегии" : "Strategy type"}>
              {isRu ? `Стратегия: ${stratType.ru}` : `Strategy: ${stratType.en}`}
            </span>
            <span className={`rounded px-2 py-0.5 text-xs ${risk.color}`} title={isRu ? "Уровень риска" : "Risk level"}>
              {isRu ? `Риск: ${risk.ru}` : `Risk: ${risk.en}`}
            </span>
            {strategy.ai_score != null && (
              <span className="text-xs text-yellow-400" title={isRu ? "AI рейтинг качества" : "AI quality rating"}>
                {(strategy.ai_score * 100).toFixed(0)}%
              </span>
            )}
            <span className="text-xs text-text-muted" title={isRu ? "Подписчиков" : "Subscribers"}>
              {strategy.subscriber_count} {isRu ? "подписчиков" : "subscribers"}
            </span>
          </div>
          {strategy.description && <p className="text-sm text-text-secondary line-clamp-2">{strategy.description}</p>}
        </div>
        <PriceBadge type={strategy.price_type} price={strategy.price_monthly} isRu={isRu} />
      </div>

      {/* Tags */}
      {tags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {tags.map((tag) => <span key={tag} className="rounded bg-surface-hover px-2 py-0.5 text-xs text-text-muted">{tag}</span>)}
        </div>
      )}

      {/* Metrics */}
      <div className="mt-4 grid grid-cols-5 gap-4 text-sm">
        <Metric
          label={isRu ? "Винрейт" : "Win Rate"}
          value={strategy.win_rate !== null ? `${(strategy.win_rate * 100).toFixed(0)}%` : "—"}
          color={strategy.win_rate !== null ? (strategy.win_rate >= 0.65 ? "text-green-400" : strategy.win_rate >= 0.5 ? "text-yellow-400" : "text-red-400") : "text-text-muted"}
        />
        <Metric
          label={isRu ? "Ср. прибыль" : "Avg Profit"}
          value={strategy.avg_profit !== null ? `${strategy.avg_profit >= 0 ? "+" : ""}${strategy.avg_profit.toFixed(1)}%` : "—"}
          color={strategy.avg_profit !== null ? (strategy.avg_profit >= 0 ? "text-green-400" : "text-red-400") : "text-text-muted"}
        />
        <Metric
          label="Sharpe"
          value={strategy.sharpe_ratio?.toFixed(1) ?? "—"}
          color={strategy.sharpe_ratio !== null ? (strategy.sharpe_ratio! >= 5 ? "text-green-400" : strategy.sharpe_ratio! >= 2 ? "text-yellow-400" : "text-text-secondary") : "text-text-muted"}
        />
        <Metric
          label={isRu ? "Сигналов" : "Signals"}
          value={String(strategy.total_signals)}
        />
        <Metric
          label={isRu ? "AI качество" : "AI Quality"}
          value={strategy.ai_score !== null ? `${(strategy.ai_score * 100).toFixed(0)}%` : "—"}
          color={strategy.ai_score !== null ? (strategy.ai_score >= 0.8 ? "text-green-400" : strategy.ai_score >= 0.6 ? "text-yellow-400" : "text-red-400") : "text-text-muted"}
        />
      </div>
    </Link>
  );
}

function Metric({ label, value, color = "text-text-primary" }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <p className="text-xs text-text-muted">{label}</p>
      <p className={`font-bold ${color}`}>{value}</p>
    </div>
  );
}

function PriceBadge({ type, price, isRu }: { type: string; price: number; isRu: boolean }) {
  if (type === "free") return <span className="flex-shrink-0 rounded bg-green-500/20 px-3 py-1 text-xs font-bold text-green-400">{isRu ? "БЕСПЛАТНО" : "FREE"}</span>;
  if (type === "premium") return <span className="flex-shrink-0 rounded bg-brand-500/20 px-3 py-1 text-xs font-bold text-brand-500">PREMIUM</span>;
  return <span className="flex-shrink-0 rounded bg-yellow-500/20 px-3 py-1 text-xs font-bold text-yellow-400">{isRu ? `${(price * 90).toLocaleString("ru-RU")} ₽/мес` : `$${price}/mo`}</span>;
}
