import type { Provider } from "@/types";
import { formatPercent, formatConfidence, confidenceColor } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";

export function ProviderCard({ provider, rank }: { provider: Provider; rank: number }) {
  const { t } = useI18n();

  const rankDisplay = rank <= 3
    ? ["1", "2", "3"][rank - 1]
    : String(rank);
  const rankColor = rank === 1
    ? "bg-yellow-500/20 text-yellow-400 border-yellow-500/30"
    : rank === 2
      ? "bg-gray-400/20 text-gray-300 border-gray-400/30"
      : rank === 3
        ? "bg-orange-500/20 text-orange-400 border-orange-500/30"
        : "bg-surface text-text-muted border-border";

  return (
    <div className="flex items-center gap-4 rounded-xl border border-border bg-surface-card p-4 transition hover:border-brand-500/30">
      {/* Rank */}
      <div className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full border text-lg font-bold ${rankColor}`}>
        {rankDisplay}
      </div>

      {/* Name + info */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <h3 className="truncate font-semibold text-text-primary">{provider.name}</h3>
          <span className="rounded bg-surface-hover px-1.5 py-0.5 text-xs text-text-muted">{provider.source}</span>
        </div>
        <p className="text-xs text-text-muted">{provider.total_signals} {t("providers.signals")}</p>
      </div>

      {/* Stats */}
      <div className="flex gap-4 text-right text-sm">
        <Stat label={t("providers.winRate")} value={provider.win_rate !== null ? `${(provider.win_rate * 100).toFixed(0)}%` : "—"} />
        <Stat
          label={t("providers.avgProfit")}
          value={provider.avg_profit !== null ? `${provider.avg_profit >= 0 ? "+" : ""}${provider.avg_profit.toFixed(1)}%` : "—"}
          color={provider.avg_profit !== null ? (provider.avg_profit >= 0 ? "text-green-400" : "text-red-400") : undefined}
        />
        <Stat label={t("providers.sharpe")} value={provider.sharpe_ratio?.toFixed(2) ?? "—"} />
        <Stat label={t("providers.profitFactor")} value={provider.profit_factor?.toFixed(1) ?? "—"} />
        <Stat
          label={t("providers.drawdown")}
          value={provider.max_drawdown !== null ? `${provider.max_drawdown.toFixed(1)}%` : "—"}
          color={provider.max_drawdown !== null && provider.max_drawdown < -20 ? "text-red-400" : undefined}
        />
        <div>
          <p className="text-xs text-text-muted">{t("providers.aiScore")}</p>
          <p className={`text-lg font-bold ${confidenceColor(provider.ai_score)}`}>{formatConfidence(provider.ai_score)}</p>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (<div><p className="text-xs text-text-muted">{label}</p><p className={`font-semibold ${color || "text-text-primary"}`}>{value}</p></div>);
}
