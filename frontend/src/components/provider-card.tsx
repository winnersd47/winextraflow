import type { Provider } from "@/types";
import { formatPercent, formatConfidence, confidenceColor } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";

export function ProviderCard({ provider, rank }: { provider: Provider; rank: number }) {
  const { t } = useI18n();
  return (
    <div className="flex items-center gap-4 rounded-xl border border-gray-800 bg-surface-card p-4 transition hover:border-gray-700">
      <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-surface text-lg font-bold text-gray-400">
        {rank <= 3 ? ["🥇", "🥈", "🥉"][rank - 1] : `#${rank}`}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <h3 className="truncate font-semibold text-white">{provider.name}</h3>
          <span className="rounded bg-gray-700 px-1.5 py-0.5 text-xs text-gray-400">{provider.source}</span>
        </div>
        <p className="text-xs text-gray-500">{provider.total_signals} {t("providers.signals")}</p>
      </div>
      <div className="flex gap-4 text-right text-sm">
        <Stat label={t("providers.winRate")} value={provider.win_rate !== null ? `${(provider.win_rate * 100).toFixed(0)}%` : "—"} />
        <Stat label={t("providers.sharpe")} value={provider.sharpe_ratio?.toFixed(2) ?? "—"} />
        <Stat label="PF" value={provider.profit_factor?.toFixed(1) ?? "—"} />
        <Stat label={t("providers.drawdown")} value={provider.max_drawdown !== null ? `${provider.max_drawdown.toFixed(1)}%` : "—"} color={provider.max_drawdown !== null && provider.max_drawdown < -20 ? "text-red-400" : undefined} />
        <div>
          <p className="text-xs text-gray-500">{t("providers.aiScore")}</p>
          <p className={`text-lg font-bold ${confidenceColor(provider.ai_score)}`}>{formatConfidence(provider.ai_score)}</p>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (<div><p className="text-xs text-gray-500">{label}</p><p className={`font-semibold ${color || "text-white"}`}>{value}</p></div>);
}
