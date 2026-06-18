"use client";

import Link from "next/link";
import type { Signal } from "@/types";
import { RatingBadge } from "./rating-badge";
import { Sparkline } from "./sparkline";
import { useI18n } from "@/lib/i18n";
import { actionColor, formatPrice, formatPercent, timeAgo } from "@/lib/utils";

/**
 * Calculate estimated profit/loss based on entry, TP, SL, and signal action.
 */
function estimatedProfit(signal: Signal): { pct: number | null; label: string; color: string } {
  // If already closed — show real profit
  if (signal.profit_pct !== null) {
    return {
      pct: signal.profit_pct,
      label: formatPercent(signal.profit_pct),
      color: signal.profit_pct >= 0 ? "text-green-400" : "text-red-400",
    };
  }
  // For active signals — estimate based on TP
  if (signal.take_profit && signal.entry_price > 0) {
    const pct = signal.action === "buy"
      ? ((signal.take_profit - signal.entry_price) / signal.entry_price) * 100
      : ((signal.entry_price - signal.take_profit) / signal.entry_price) * 100;
    return {
      pct,
      label: `~${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`,
      color: pct >= 0 ? "text-green-400" : "text-yellow-400",
    };
  }
  return { pct: null, label: "—", color: "text-text-muted" };
}

export function SignalCard({ signal, strategyLabel, regimeLabel }: { signal: Signal; strategyLabel?: string; regimeLabel?: string }) {
  const isActive = signal.status === "active";
  const isProfitable = signal.profit_pct !== null && signal.profit_pct > 0;
  const isSimulation = signal.ai_reasoning?.includes("[SIMULATION]") || (signal as any).raw_message?.includes("[SIMULATION]");
  const { t } = useI18n();
  const profit = estimatedProfit(signal);

  return (
    <Link
      href={`/dashboard/signals/${signal.id}`}
      className="block rounded-xl border border-border bg-surface-card p-4 transition hover:border-brand-500/40 hover:bg-surface-hover stat-glow"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold text-text-primary">{signal.ticker}</span>
          <span className={`rounded px-2 py-0.5 text-xs font-bold uppercase ${actionColor(signal.action)} ${signal.action === "buy" ? "bg-green-500/10" : "bg-red-500/10"}`}>
            {signal.action}
          </span>
          <RatingBadge confidence={signal.ai_confidence} />
          {isSimulation && <span className="rounded bg-orange-500/20 px-2 py-0.5 text-xs font-bold text-orange-400">симуляция</span>}
          {strategyLabel && (
            <span className="rounded bg-purple-500/10 px-2 py-0.5 text-xs text-purple-400">{strategyLabel}</span>
          )}
          {regimeLabel && (
            <span className="rounded bg-blue-500/10 px-2 py-0.5 text-xs text-blue-400">{regimeLabel}</span>
          )}
        </div>
        <span className="text-xs text-text-muted">{timeAgo(signal.created_at)}</span>
      </div>
      <div className="mt-3 grid grid-cols-5 gap-3 text-sm">
        <div>
          <span className="text-text-muted">{t("signals.entry")}</span>
          <p className="font-medium text-text-primary">{formatPrice(signal.entry_price)}</p>
        </div>
        <div>
          <span className="text-text-muted">TP</span>
          <p className="font-medium text-green-400">{signal.take_profit ? formatPrice(signal.take_profit) : "—"}</p>
        </div>
        <div>
          <span className="text-text-muted">SL</span>
          <p className="font-medium text-red-400">{signal.stop_loss ? formatPrice(signal.stop_loss) : "—"}</p>
        </div>
        <div>
          <span className="text-text-muted">{t("signals.status")}</span>
          <p className={`font-medium ${isActive ? "text-blue-400" : isProfitable ? "text-green-400" : "text-red-400"}`}>
            {isActive ? t(`status.${signal.status}`) : formatPercent(signal.profit_pct)}
          </p>
        </div>
        {/* Estimated Profit — accent column with sparkline */}
        <div className="rounded-lg bg-surface px-2 py-1 text-center">
          <span className="text-text-muted text-xs">{t("signals.estProfit")}</span>
          <p className={`text-base font-bold ${profit.color}`}>
            {profit.label}
          </p>
          {signal.entry_price > 0 && (
            <Sparkline
              data={[
                signal.stop_loss || signal.entry_price * 0.97,
                signal.entry_price,
                signal.take_profit || signal.entry_price * 1.03,
              ]}
              width={60}
              height={16}
              color={signal.action === "buy" ? "#10b981" : "#ef4444"}
            />
          )}
        </div>
      </div>
    </Link>
  );
}
