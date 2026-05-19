"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { RatingBadge } from "@/components/rating-badge";
import {
  actionColor,
  formatPrice,
  formatPercent,
  formatConfidence,
  confidenceColor,
  timeAgo,
} from "@/lib/utils";
import type { Signal, RatingDetail } from "@/types";

export default function SignalDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { t, locale } = useI18n();
  const isRu = locale === "ru";
  const [signal, setSignal] = useState<Signal | null>(null);
  const [rating, setRating] = useState<RatingDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [s, r] = await Promise.all([api.getSignal(id), api.getSignalRating(id)]);
        setSignal(s);
        setRating(r);
      } catch (err) { console.error(err); }
      finally { setLoading(false); }
    }
    load();
  }, [id]);

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;
  if (!signal) return <div className="py-20 text-center text-text-secondary">{t("signals.empty")}</div>;

  return (
    <div className="mx-auto max-w-3xl">
      <button onClick={() => router.back()} className="mb-4 text-sm text-text-secondary hover:text-text-primary">&larr; {t("signals.back")}</button>

      <div className="rounded-xl border border-border bg-surface-card p-6">
        <div className="flex items-center gap-3">
          <h1 className="text-3xl font-bold text-text-primary">{signal.ticker}</h1>
          <span className={`rounded px-3 py-1 text-sm font-bold uppercase ${actionColor(signal.action)} ${signal.action === "buy" ? "bg-green-500/10" : "bg-red-500/10"}`}>{signal.action}</span>
          <RatingBadge confidence={signal.ai_confidence} size="lg" />
          <span className="ml-auto text-sm text-text-muted">{timeAgo(signal.created_at)}</span>
        </div>

        {signal.ai_reasoning && <p className="mt-2 text-sm text-text-secondary">
          {isRu ? signal.ai_reasoning
            .replace("Strong:", "Сильные:")
            .replace("Average quality across factors", "Среднее качество по всем факторам")
            .replace("Weak:", "Слабые:")
            .replace("good risk management", "хороший риск-менеджмент")
            .replace("reliable provider", "надёжный провайдер")
            .replace("missing TP/SL or low provider history", "отсутствует TP/SL или мало истории провайдера")
            : signal.ai_reasoning}
        </p>}

        {/* Execute button */}
        {signal.status === "active" && (
          <button
            onClick={async () => {
              try {
                const accounts = await api.getExchangeAccounts();
                if (accounts.length === 0) { alert(t("signals.noAccounts")); return; }
                const result = await api.executeSignal(signal.id, accounts[0].id);
                alert(`${t("signals.executed")}: ${result.status}`);
              } catch (err: any) { alert(err.message); }
            }}
            className="mt-3 rounded-lg bg-brand-600 px-6 py-2 text-sm font-medium text-white hover:bg-brand-700"
          >
            {t("signals.executeSignal")}
          </button>
        )}

        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Stat label={t("signals.entry")} value={formatPrice(signal.entry_price)} />
          <Stat label="Take Profit" value={signal.take_profit ? formatPrice(signal.take_profit) : "—"} color="text-green-400" />
          <Stat label="Stop Loss" value={signal.stop_loss ? formatPrice(signal.stop_loss) : "—"} color="text-red-400" />
          <Stat label={t("signals.status")} value={t(`status.${signal.status}`)} />
        </div>

        {signal.profit_pct !== null && (
          <div className="mt-4 rounded-lg bg-surface p-4">
            <div className="flex items-center justify-between">
              <span className="text-text-secondary">{t("signals.result")}</span>
              <span className={`text-2xl font-bold ${signal.profit_pct >= 0 ? "text-green-400" : "text-red-400"}`}>{formatPercent(signal.profit_pct)}</span>
            </div>
            {signal.close_price && <p className="mt-1 text-sm text-text-muted">{t("signals.closedAt")} {formatPrice(signal.close_price)}</p>}
          </div>
        )}
      </div>

      {rating && (
        <div className="mt-6 rounded-xl border border-border bg-surface-card p-6">
          <h2 className="mb-4 text-lg font-bold text-text-primary">{t("signals.aiRating")}</h2>
          <div className="mb-4 flex items-center gap-3">
            <span className="text-3xl font-bold text-text-primary">{formatConfidence(rating.final_confidence)}</span>
            <span className={`text-sm ${confidenceColor(rating.final_confidence)}`}>{isRu ? "уверенность" : "confidence"}</span>
          </div>
          <p className="mb-6 text-sm text-text-secondary">
            {isRu ? (rating.reasoning || "")
              .replace("Strong:", "Сильные:")
              .replace("Average quality across factors", "Среднее качество по факторам")
              .replace("Weak:", "Слабые:")
              .replace("good risk management", "хороший риск-менеджмент")
              .replace("reliable provider", "надёжный провайдер")
              .replace("provider history", "история провайдера")
              .replace("sharpe ratio", "коэффициент Шарпа")
              .replace("profit factor", "профит-фактор")
              .replace("signal frequency", "частота сигналов")
              : rating.reasoning}
          </p>
          <div className="space-y-3">
            {Object.entries(rating.factors).map(([key, factor]) => {
              const factorNamesRu: Record<string, string> = {
                risk_management: "Риск-менеджмент",
                risk_reward: "Риск/Прибыль",
                provider_history: "История провайдера",
                sharpe_ratio: "Коэффициент Шарпа",
                profit_factor: "Профит-фактор",
                max_drawdown: "Макс. просадка",
                signal_frequency: "Частота сигналов",
                time_decay: "Свежесть данных",
                completeness: "Полнота данных",
              };
              const factorName = isRu ? (factorNamesRu[key] || key.replace(/_/g, " ")) : key.replace(/_/g, " ");

              // Translate factor reasons
              const reasonRu = (reason: string) => reason
                .replace("Both TP and SL defined", "TP и SL заданы")
                .replace("Only TP defined", "Задан только TP")
                .replace("Only SL defined", "Задан только SL")
                .replace("No TP or SL", "TP и SL не заданы")
                .replace("partial risk management", "частичный риск-менеджмент")
                .replace("full risk management", "полный риск-менеджмент")
                .replace("no risk management", "нет риск-менеджмента")
                .replace("Cannot calculate R:R", "Невозможно рассчитать R:R")
                .replace("missing TP or SL", "отсутствует TP или SL")
                .replace("Excellent win rate:", "Отличный винрейт:")
                .replace("Good win rate:", "Хороший винрейт:")
                .replace("Average win rate:", "Средний винрейт:")
                .replace("Low win rate:", "Низкий винрейт:")
                .replace("No provider history", "Нет истории провайдера")
                .replace("Excellent Sharpe ratio:", "Отличный Шарп:")
                .replace("Good Sharpe ratio:", "Хороший Шарп:")
                .replace("Low Sharpe ratio:", "Низкий Шарп:")
                .replace("No Sharpe data", "Нет данных по Шарпу")
                .replace("Excellent profit factor:", "Отличный профит-фактор:")
                .replace("Good profit factor:", "Хороший профит-фактор:")
                .replace("Low profit factor:", "Низкий профит-фактор:")
                .replace("No profit factor data", "Нет данных")
                .replace("Normal frequency", "Нормальная частота")
                .replace("High frequency", "Высокая частота")
                .replace("signals in last 24h", "сигналов за 24ч")
                .replace("R:R ratio:", "Соотношение R:R:");

              return (
              <div key={key} className="rounded-lg bg-surface p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-text-primary">{factorName}</span>
                  <span className="text-sm text-text-secondary">{(factor.weight * 100).toFixed(0)}%</span>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-hover">
                  <div className="h-full rounded-full bg-brand-500 transition-all" style={{ width: `${factor.score * 100}%` }} />
                </div>
                <p className="mt-1 text-xs text-text-muted">{isRu ? reasonRu(factor.reason) : factor.reason}</p>
              </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, color = "text-text-primary" }: { label: string; value: string; color?: string }) {
  return (<div><span className="text-xs text-text-muted">{label}</span><p className={`text-lg font-semibold ${color}`}>{value}</p></div>);
}
