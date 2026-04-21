import Link from "next/link";
import type { StrategyResponse } from "@/types";
import { useI18n } from "@/lib/i18n";
import { formatConfidence, confidenceColor } from "@/lib/utils";

export function StrategyCard({ strategy }: { strategy: StrategyResponse }) {
  const { t } = useI18n();
  const tags = strategy.tags?.split(",").map((t) => t.trim()).filter(Boolean) || [];

  return (
    <Link href={`/dashboard/marketplace/${strategy.id}`} className="block rounded-xl border border-gray-800 bg-surface-card p-5 transition hover:border-gray-700 hover:bg-surface-hover">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-bold text-white">{strategy.name}</h3>
          {strategy.description && <p className="mt-1 text-sm text-gray-400 line-clamp-2">{strategy.description}</p>}
        </div>
        <PriceBadge type={strategy.price_type} price={strategy.price_monthly} t={t} />
      </div>
      {tags.length > 0 && <div className="mt-3 flex flex-wrap gap-1">{tags.map((tag) => <span key={tag} className="rounded bg-gray-700 px-2 py-0.5 text-xs text-gray-300">{tag}</span>)}</div>}
      <div className="mt-4 flex items-center gap-6 text-sm">
        <S label={t("providers.aiScore")} value={formatConfidence(strategy.ai_score)} color={confidenceColor(strategy.ai_score)} />
        <S label={t("providers.winRate")} value={strategy.win_rate !== null ? `${(strategy.win_rate * 100).toFixed(0)}%` : "—"} />
        <S label={t("providers.sharpe")} value={strategy.sharpe_ratio?.toFixed(2) ?? "—"} />
        <S label={t("providers.signals")} value={String(strategy.total_signals)} />
        <S label={t("marketplace.subscribers")} value={String(strategy.subscriber_count)} color="text-brand-500" />
      </div>
    </Link>
  );
}

function S({ label, value, color = "text-white" }: { label: string; value: string; color?: string }) {
  return <div><p className="text-xs text-gray-500">{label}</p><p className={`font-semibold ${color}`}>{value}</p></div>;
}

function PriceBadge({ type, price, t }: { type: string; price: number; t: (k: string) => string }) {
  if (type === "free") return <span className="rounded bg-green-500/20 px-2 py-1 text-xs font-bold text-green-400">{t("marketplace.free").toUpperCase()}</span>;
  if (type === "premium") return <span className="rounded bg-purple-500/20 px-2 py-1 text-xs font-bold text-purple-400">PREMIUM</span>;
  return <span className="rounded bg-yellow-500/20 px-2 py-1 text-xs font-bold text-yellow-400">${price}/mo</span>;
}
