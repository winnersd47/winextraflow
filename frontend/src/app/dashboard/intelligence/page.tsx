"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";

const REGIME_COLORS: Record<string, string> = {
  trending_up: "text-green-400 bg-green-500/10",
  trending_down: "text-red-400 bg-red-500/10",
  ranging: "text-blue-400 bg-blue-500/10",
  high_volatility: "text-orange-400 bg-orange-500/10",
  low_volatility: "text-gray-400 bg-gray-500/10",
  breakout: "text-yellow-400 bg-yellow-500/10",
  unknown: "text-text-muted bg-surface",
};

const REGIME_RU: Record<string, string> = {
  trending_up: "Восходящий тренд",
  trending_down: "Нисходящий тренд",
  ranging: "Боковик",
  high_volatility: "Высокая волатильность",
  low_volatility: "Низкая волатильность",
  breakout: "Пробой",
  unknown: "Не определён",
};

const REC_COLORS: Record<string, string> = {
  strong_buy: "text-green-400 bg-green-500/20",
  buy: "text-green-300 bg-green-500/10",
  neutral: "text-gray-400 bg-gray-500/10",
  avoid: "text-orange-400 bg-orange-500/10",
  strong_avoid: "text-red-400 bg-red-500/10",
};

export default function IntelligencePage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const { locale } = useI18n();
  const isRu = locale === "ru";

  useEffect(() => {
    const load = async () => {
      try {
        const token = localStorage.getItem("token");
        const resp = await fetch("/api/v1/quant/dashboard", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (resp.ok) setData(await resp.json());
      } catch {}
      finally { setLoading(false); }
    };
    load();
  }, []);

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;
  if (!data) return <div className="py-20 text-center text-text-muted">Failed to load intelligence data</div>;

  const { market, ticker_regimes, evaluations, architecture_level, architecture_levels } = data;

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="mb-2 text-2xl font-bold text-text-primary">
        {isRu ? "Рыночная аналитика" : "Market Intelligence"}
      </h1>
      <p className="mb-6 text-sm text-text-secondary">
        {isRu ? "Автономная система анализа рынка. Уровень архитектуры: " : "Autonomous market analysis system. Architecture level: "}
        <span className="font-bold text-brand-500">L{architecture_level}</span>
      </p>

      {/* Market Regime */}
      <div className="mb-6 rounded-xl border border-border bg-surface-card p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-text-muted">{isRu ? "Текущий режим рынка" : "Current Market Regime"}</p>
            <div className="mt-1 flex items-center gap-3">
              <span className={`rounded-lg px-4 py-2 text-lg font-bold ${REGIME_COLORS[market.regime] || REGIME_COLORS.unknown}`}>
                {isRu ? (REGIME_RU[market.regime] || market.regime) : market.regime.replace("_", " ")}
              </span>
              <span className="text-sm text-text-muted">{(market.confidence * 100).toFixed(0)}% {isRu ? "уверенность" : "confidence"}</span>
            </div>
          </div>
          <div className="text-right">
            <p className="text-xs text-text-muted">{isRu ? "Волатильность" : "Volatility"}</p>
            <p className="text-2xl font-bold text-text-primary">{market.volatility.toFixed(1)}</p>
            <p className="text-xs text-text-muted">{market.signal_frequency.toFixed(1)} {isRu ? "сигн/час" : "sig/hr"}</p>
          </div>
        </div>
      </div>

      {/* Ticker Regimes */}
      {Object.keys(ticker_regimes).length > 0 && (
        <div className="mb-6">
          <h2 className="mb-3 text-lg font-bold text-text-primary">{isRu ? "Режимы по тикерам" : "Ticker Regimes"}</h2>
          <div className="flex flex-wrap gap-2">
            {Object.entries(ticker_regimes).map(([ticker, info]: [string, any]) => (
              <div key={ticker} className={`rounded-lg px-3 py-2 ${REGIME_COLORS[info.regime] || REGIME_COLORS.unknown}`}>
                <span className="text-xs font-bold">{ticker}</span>
                <span className="ml-2 text-xs opacity-80">
                  {isRu ? (REGIME_RU[info.regime] || info.regime) : info.regime.replace("_", " ")}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Signal Evaluations */}
      <div className="mb-6">
        <h2 className="mb-3 text-lg font-bold text-text-primary">{isRu ? "AI-оценка последних сигналов" : "AI Evaluation of Recent Signals"}</h2>
        <div className="space-y-2">
          {evaluations.map((e: any) => (
            <div key={e.signal_id} className="flex items-center justify-between rounded-xl border border-border bg-surface-card p-4">
              <div className="flex items-center gap-3">
                <span className="text-sm font-bold text-text-primary">{e.ticker}</span>
                <span className="rounded bg-surface-hover px-2 py-0.5 text-xs text-text-muted">
                  {isRu ? e.strategy_name_ru : e.strategy_name}
                </span>
                <span className={`rounded px-2 py-0.5 text-xs ${REGIME_COLORS[e.regime] || ""}`}>
                  {isRu ? (REGIME_RU[e.regime] || e.regime) : e.regime.replace("_", " ")}
                </span>
                {!e.regime_compatible && (
                  <span className="rounded bg-red-500/10 px-2 py-0.5 text-xs text-red-400">
                    {isRu ? "Режим не подходит" : "Regime mismatch"}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <p className="text-xs text-text-muted">Meta Score</p>
                  <p className="text-lg font-bold text-text-primary">{(e.meta_score * 100).toFixed(0)}%</p>
                </div>
                <span className={`rounded-lg px-3 py-1.5 text-xs font-bold ${REC_COLORS[e.recommendation] || ""}`}>
                  {isRu ? e.recommendation_ru : e.recommendation.replace("_", " ")}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Architecture Levels */}
      <div className="rounded-xl border border-border bg-surface-card p-6">
        <h2 className="mb-4 text-lg font-bold text-text-primary">{isRu ? "Уровни архитектуры" : "Architecture Levels"}</h2>
        <div className="space-y-2">
          {Object.entries(architecture_levels).map(([level, desc]: [string, any]) => {
            const isCurrent = parseInt(level) === architecture_level;
            const isPlanned = parseInt(level) > architecture_level;
            return (
              <div key={level} className={`flex items-center gap-3 rounded-lg p-3 ${isCurrent ? "border-2 border-brand-500 bg-brand-500/5" : "bg-surface"}`}>
                <span className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold ${isCurrent ? "bg-brand-500 text-white" : isPlanned ? "bg-surface-hover text-text-muted" : "bg-green-500/20 text-green-400"}`}>
                  L{level}
                </span>
                <span className={`text-sm ${isCurrent ? "font-bold text-brand-500" : isPlanned ? "text-text-muted" : "text-text-secondary"}`}>
                  {desc}
                </span>
                {isCurrent && <span className="rounded bg-brand-500/20 px-2 py-0.5 text-xs font-bold text-brand-500">{isRu ? "ТЕКУЩИЙ" : "CURRENT"}</span>}
              </div>
            );
          })}
        </div>
      </div>

      {/* Disclaimer */}
      <div className="mt-6 rounded-lg border border-border bg-surface-card px-4 py-3 text-xs text-text-muted">
        {isRu
          ? "Рыночная аналитика основана на внутренних данных платформы и НЕ является инвестиционной рекомендацией. Режимы и оценки носят информационный характер."
          : "Market analytics are based on internal platform data and are NOT investment advice. Regimes and evaluations are for informational purposes only."}
      </div>
    </div>
  );
}
