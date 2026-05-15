"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";
import { useAuth } from "@/lib/auth";

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
  trending_up: "Восходящий тренд", trending_down: "Нисходящий тренд", ranging: "Боковик",
  high_volatility: "Высокая волатильность", low_volatility: "Низкая волатильность",
  breakout: "Пробой", unknown: "Не определён",
};
const REGIME_HINT_RU: Record<string, string> = {
  trending_up: "Рынок движется вверх. Сигналы на покупку имеют повышенную вероятность успеха. Стратегии: Trend Following, Breakout.",
  trending_down: "Рынок движется вниз. Сигналы на продажу имеют повышенную вероятность успеха. Стратегии: Trend Following, Breakout.",
  ranging: "Рынок в боковом движении. Эффективны стратегии возврата к среднему и диапазонной торговли. Пробойные стратегии рискованны.",
  high_volatility: "Высокая волатильность — повышенный риск. Рекомендуется уменьшить размер позиций и расширить стоп-лоссы.",
  low_volatility: "Низкая волатильность — рынок спокоен. Подходит для статистического арбитража и точных входов.",
  breakout: "Формируется пробой из консолидации. Высокий потенциал, но остерегайтесь ложных пробоев.",
  unknown: "Недостаточно данных для определения режима. Подождите накопления сигналов.",
};
const REGIME_HINT_EN: Record<string, string> = {
  trending_up: "Market moving up. Buy signals have higher probability of success. Strategies: Trend Following, Breakout.",
  trending_down: "Market moving down. Sell signals have higher probability of success. Strategies: Trend Following, Breakout.",
  ranging: "Market in sideways movement. Mean reversion and range strategies are effective. Breakout strategies are risky.",
  high_volatility: "High volatility — increased risk. Reduce position sizes and widen stop-losses.",
  low_volatility: "Low volatility — calm market. Good for statistical arbitrage and precise entries.",
  breakout: "Breakout forming from consolidation. High potential but watch for false breakouts.",
  unknown: "Not enough data to determine regime. Wait for signal accumulation.",
};
const REC_COLORS: Record<string, string> = {
  strong_buy: "text-green-400 bg-green-500/20", buy: "text-green-300 bg-green-500/10",
  neutral: "text-gray-400 bg-gray-500/10", avoid: "text-orange-400 bg-orange-500/10",
  strong_avoid: "text-red-400 bg-red-500/10",
};

export default function IntelligencePage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showGuide, setShowGuide] = useState(false);
  const { locale } = useI18n();
  const { user } = useAuth();
  const isRu = locale === "ru";
  const isPremium = user?.role === "premium" || user?.role === "admin";

  useEffect(() => {
    const load = async () => {
      try {
        const token = localStorage.getItem("token");
        const resp = await fetch("/api/v1/quant/dashboard", { headers: { Authorization: `Bearer ${token}` } });
        if (resp.ok) setData(await resp.json());
      } catch {}
      finally { setLoading(false); }
    };
    load();
  }, []);

  if (loading) return <div className="flex justify-center py-20"><div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" /></div>;
  if (!data) return <div className="py-20 text-center text-text-muted">Failed to load</div>;

  const { market, ticker_regimes, evaluations, top_quality, architecture_level, architecture_levels } = data;

  return (
    <div className="mx-auto max-w-5xl">
      {/* Header */}
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">
            {isRu ? "Рыночная аналитика" : "Market Intelligence"}
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            {isRu
              ? "Автоматический анализ рынка на основе всех сигналов платформы. Помогает понять текущее состояние рынка и оценить качество сигналов перед принятием решений."
              : "Automatic market analysis based on all platform signals. Helps understand current market conditions and evaluate signal quality before making decisions."}
          </p>
        </div>
        <button
          onClick={() => setShowGuide(!showGuide)}
          className="flex-shrink-0 rounded-lg border border-border px-4 py-2 text-sm text-text-secondary hover:bg-surface-hover"
        >
          {isRu ? (showGuide ? "Скрыть инструкцию" : "Как пользоваться?") : (showGuide ? "Hide guide" : "How to use?")}
        </button>
      </div>

      {/* ═══ HOW-TO GUIDE ═══ */}
      {showGuide && (
        <div className="mb-6 rounded-xl border border-brand-500/30 bg-brand-500/5 p-6">
          <h2 className="mb-4 text-lg font-bold text-text-primary">
            {isRu ? "Как пользоваться аналитикой" : "How to use Intelligence"}
          </h2>
          <div className="space-y-4 text-sm text-text-secondary">
            {isRu ? (
              <>
                <div>
                  <h3 className="font-bold text-text-primary">1. Режим рынка — определите контекст</h3>
                  <p>Посмотрите на блок "Текущий режим рынка". Это главный индикатор — он показывает, что сейчас происходит на рынке в целом. Режим определяется автоматически по всем сигналам за последние 48 часов.</p>
                  <ul className="mt-2 ml-4 list-disc space-y-1 text-text-muted">
                    <li><strong className="text-green-400">Восходящий тренд</strong> — рынок растёт. Преимущество у покупок (BUY).</li>
                    <li><strong className="text-red-400">Нисходящий тренд</strong> — рынок падает. Преимущество у продаж (SELL).</li>
                    <li><strong className="text-blue-400">Боковик</strong> — нет чёткого направления. Работайте от уровней поддержки/сопротивления.</li>
                    <li><strong className="text-orange-400">Высокая волатильность</strong> — повышенный риск. Уменьшите размер позиций.</li>
                    <li><strong className="text-yellow-400">Пробой</strong> — возможен сильный импульс. Следите за подтверждением.</li>
                  </ul>
                </div>
                <div>
                  <h3 className="font-bold text-text-primary">2. Режимы по тикерам — детализация</h3>
                  <p>Каждый тикер может находиться в своём режиме. Например, BTCUSDT может быть в тренде, а EURUSD — в боковике. Это помогает выбирать, какие сигналы более актуальны.</p>
                </div>
                <div>
                  <h3 className="font-bold text-text-primary">3. AI-оценка сигналов (Premium)</h3>
                  <p>Для каждого последнего сигнала система показывает:</p>
                  <ul className="mt-2 ml-4 list-disc space-y-1 text-text-muted">
                    <li><strong>Тип стратегии</strong> — как классифицирован сигнал (Trend Following, Breakout, ML/AI и др.)</li>
                    <li><strong>Качество сигнала</strong> — интегральная оценка (0-100%). Учитывает AI-уверенность, историю провайдера, соотношение риск/прибыль, совместимость с режимом рынка.</li>
                    <li><strong>Рекомендация</strong> — от "Уверенная покупка" до "Категорически избегать".</li>
                    <li><strong>Совместимость с режимом</strong> — красная метка если стратегия не подходит текущему состоянию рынка.</li>
                  </ul>
                </div>
                <div>
                  <h3 className="font-bold text-text-primary">4. Практические действия</h3>
                  <ul className="mt-2 ml-4 list-disc space-y-1 text-text-muted">
                    <li>Если режим = "Высокая волатильность" → уменьшите размер позиций на 50%</li>
                    <li>Если Качество сигнала ниже 40% → лучше пропустить сделку</li>
                    <li>Если "Режим не подходит" → стратегия сигнала не совместима с текущим рынком, риск выше</li>
                    <li>Используйте Бэктест для проверки провайдера перед подпиской на его стратегию</li>
                  </ul>
                </div>
              </>
            ) : (
              <>
                <div>
                  <h3 className="font-bold text-text-primary">1. Market Regime — establish context</h3>
                  <p>Check the "Current Market Regime" block. This is the primary indicator — it shows what's happening in the market overall. The regime is automatically detected from all signals in the last 48 hours.</p>
                  <ul className="mt-2 ml-4 list-disc space-y-1 text-text-muted">
                    <li><strong className="text-green-400">Trending Up</strong> — market is rising. Buy signals have an edge.</li>
                    <li><strong className="text-red-400">Trending Down</strong> — market is falling. Sell signals have an edge.</li>
                    <li><strong className="text-blue-400">Ranging</strong> — no clear direction. Trade support/resistance levels.</li>
                    <li><strong className="text-orange-400">High Volatility</strong> — increased risk. Reduce position sizes.</li>
                    <li><strong className="text-yellow-400">Breakout</strong> — potential strong move. Wait for confirmation.</li>
                  </ul>
                </div>
                <div>
                  <h3 className="font-bold text-text-primary">2. Ticker Regimes — drill down</h3>
                  <p>Each ticker can be in its own regime. For example, BTCUSDT may be trending while EURUSD is ranging. This helps you prioritize which signals are most relevant.</p>
                </div>
                <div>
                  <h3 className="font-bold text-text-primary">3. AI Signal Evaluation (Premium)</h3>
                  <p>For each recent signal the system shows: Strategy type, Signal Quality (0-100%), Recommendation, and Regime compatibility.</p>
                </div>
                <div>
                  <h3 className="font-bold text-text-primary">4. Practical actions</h3>
                  <ul className="mt-2 ml-4 list-disc space-y-1 text-text-muted">
                    <li>High volatility regime → reduce position sizes by 50%</li>
                    <li>Signal Quality below 40% → consider skipping the trade</li>
                    <li>"Regime mismatch" → strategy doesn't fit current market, higher risk</li>
                    <li>Use Backtest to verify a provider before subscribing to their strategy</li>
                  </ul>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ═══ MARKET REGIME (L1 — all users) ═══ */}
      <div className="mb-6 rounded-xl border border-border bg-surface-card p-6">
        <div className="mb-2 flex items-center gap-2">
          <h2 className="text-sm font-bold text-text-muted">{isRu ? "ТЕКУЩИЙ РЕЖИМ РЫНКА" : "CURRENT MARKET REGIME"}</h2>
          <span className="rounded bg-surface-hover px-2 py-0.5 text-xs text-text-muted">L1</span>
        </div>
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3">
              <span className={`rounded-lg px-4 py-2 text-lg font-bold ${REGIME_COLORS[market.regime] || REGIME_COLORS.unknown}`}>
                {isRu ? (REGIME_RU[market.regime] || market.regime) : market.regime.replace("_", " ")}
              </span>
              <span className="text-sm text-text-muted">{(market.confidence * 100).toFixed(0)}%</span>
            </div>
            <p className="mt-2 text-xs text-text-secondary">
              {isRu ? (REGIME_HINT_RU[market.regime] || "") : (REGIME_HINT_EN[market.regime] || "")}
            </p>
          </div>
          <div className="flex gap-6 text-center">
            <div>
              <p className="text-xs text-text-muted">{isRu ? "Волатильность" : "Volatility"}</p>
              <p className="text-2xl font-bold text-text-primary">{market.volatility.toFixed(1)}</p>
            </div>
            <div>
              <p className="text-xs text-text-muted">{isRu ? "Сигн/час" : "Sig/hr"}</p>
              <p className="text-2xl font-bold text-text-primary">{market.signal_frequency.toFixed(1)}</p>
            </div>
            <div>
              <p className="text-xs text-text-muted">Buy / Sell</p>
              <p className="text-lg font-bold text-text-primary">
                <span className="text-green-400">{((market.confidence > 0 ? data.market?.buy_ratio || 0.5 : 0.5) * 100).toFixed(0)}%</span>
                {" / "}
                <span className="text-red-400">{((1 - (data.market?.buy_ratio || 0.5)) * 100).toFixed(0)}%</span>
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* ═══ TICKER REGIMES (L1) ═══ */}
      {Object.keys(ticker_regimes).length > 0 && (
        <div className="mb-6">
          <div className="mb-3 flex items-center gap-2">
            <h2 className="text-sm font-bold text-text-muted">{isRu ? "РЕЖИМЫ ПО ТИКЕРАМ" : "TICKER REGIMES"}</h2>
            <span className="rounded bg-surface-hover px-2 py-0.5 text-xs text-text-muted">L1</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(ticker_regimes).map(([ticker, info]: [string, any]) => (
              <div key={ticker} className={`rounded-lg px-3 py-2 ${REGIME_COLORS[info.regime] || REGIME_COLORS.unknown}`}>
                <span className="text-sm font-bold">{ticker}</span>
                <span className="ml-2 text-xs opacity-80">
                  {isRu ? (REGIME_RU[info.regime] || info.regime) : info.regime.replace("_", " ")}
                </span>
                <span className="ml-1 text-xs opacity-50">{(info.confidence * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ═══ SIGNAL EVALUATIONS (L2 — Premium) — two columns ═══ */}
      <div className="mb-6">
        <div className="mb-3 flex items-center gap-2">
          <h2 className="text-sm font-bold text-text-muted">{isRu ? "AI-ОЦЕНКА СИГНАЛОВ" : "AI SIGNAL EVALUATION"}</h2>
          <span className="rounded bg-brand-500/20 px-2 py-0.5 text-xs font-bold text-brand-500">L2 Premium</span>
        </div>

        {!isPremium ? (
          <div className="rounded-xl border border-border bg-surface-card p-8 text-center">
            <p className="text-text-secondary">{isRu ? "AI-оценка сигналов с классификацией стратегий и оценкой качества доступна в Premium." : "AI signal evaluation with strategy classification and Signal Quality is available in Premium."}</p>
            <a href="/dashboard/premium" className="mt-3 inline-block rounded-lg bg-brand-600 px-6 py-2 text-sm font-medium text-white hover:bg-brand-700">
              {isRu ? "Подключить Premium" : "Get Premium"}
            </a>
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {/* Left: Latest 10 signals */}
            <div>
              <h3 className="mb-2 text-xs font-bold text-text-muted">
                {isRu ? "ПОСЛЕДНИЕ СИГНАЛЫ" : "LATEST SIGNALS"} ({evaluations.length})
              </h3>
              <div className="space-y-1.5">
                {evaluations.map((e: any) => <EvalCard key={e.signal_id} e={e} isRu={isRu} />)}
              </div>
            </div>
            {/* Right: Top 10 by quality */}
            <div>
              <h3 className="mb-2 text-xs font-bold text-text-muted">
                {isRu ? "ТОП ПО КАЧЕСТВУ" : "TOP QUALITY"} ({(top_quality || []).length})
              </h3>
              <div className="space-y-1.5">
                {(top_quality || []).map((e: any, i: number) => <EvalCard key={e.signal_id} e={e} isRu={isRu} rank={i + 1} />)}
                {(!top_quality || top_quality.length === 0) && (
                  <p className="rounded-xl border border-border bg-surface-card p-4 text-center text-xs text-text-muted">
                    {isRu ? "Недостаточно данных" : "Not enough data"}
                  </p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ═══ ARCHITECTURE ROADMAP ═══ */}
      <div className="mb-6 rounded-xl border border-border bg-surface-card p-6">
        <h2 className="mb-2 text-sm font-bold text-text-muted">{isRu ? "АРХИТЕКТУРА СИСТЕМЫ" : "SYSTEM ARCHITECTURE"}</h2>
        <p className="mb-4 text-xs text-text-secondary">
          {isRu
            ? "Система анализа непрерывно эволюционирует. Каждый новый сигнал и каждая обработанная статья усиливают алгоритмы."
            : "The analysis system continuously evolves. Every new signal and processed article strengthens the algorithms."}
        </p>
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
      <div className="rounded-lg border border-border bg-surface-card px-4 py-3 text-xs text-text-muted">
        {isRu
          ? "Рыночная аналитика основана на внутренних данных платформы и НЕ является инвестиционной рекомендацией. Режимы и оценки носят информационный характер. Перед принятием торговых решений проведите собственный анализ."
          : "Market analytics are based on internal platform data and are NOT investment advice. Regimes and evaluations are for informational purposes only. Conduct your own analysis before making trading decisions."}
      </div>
    </div>
  );
}

const REGIME_COLORS_STATIC: Record<string, string> = {
  trending_up: "text-green-400 bg-green-500/10", trending_down: "text-red-400 bg-red-500/10",
  ranging: "text-blue-400 bg-blue-500/10", high_volatility: "text-orange-400 bg-orange-500/10",
  low_volatility: "text-gray-400 bg-gray-500/10", breakout: "text-yellow-400 bg-yellow-500/10",
  unknown: "text-text-muted bg-surface",
};
const REGIME_RU_STATIC: Record<string, string> = {
  trending_up: "Тренд вверх", trending_down: "Тренд вниз", ranging: "Боковик",
  high_volatility: "Выс. вол.", low_volatility: "Низк. вол.", breakout: "Пробой", unknown: "?",
};
const REC_COLORS_STATIC: Record<string, string> = {
  strong_buy: "text-green-400 bg-green-500/20", buy: "text-green-300 bg-green-500/10",
  neutral: "text-gray-400 bg-gray-500/10", avoid: "text-orange-400 bg-orange-500/10",
  strong_avoid: "text-red-400 bg-red-500/10",
};

function EvalCard({ e, isRu, rank }: { e: any; isRu: boolean; rank?: number }) {
  return (
    <div className="rounded-lg border border-border bg-surface-card p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          {rank && (
            <span className={`flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold ${
              rank <= 3 ? "bg-brand-500/20 text-brand-500" : "bg-surface text-text-muted"
            }`}>{rank}</span>
          )}
          <span className="text-sm font-bold text-text-primary">{e.ticker}</span>
          {e.action && (
            <span className={`text-xs font-bold uppercase ${e.action === "buy" ? "text-green-400" : "text-red-400"}`}>
              {e.action}
            </span>
          )}
          <span className="truncate rounded bg-purple-500/10 px-1.5 py-0.5 text-xs text-purple-400">
            {isRu ? e.strategy_name_ru : e.strategy_name}
          </span>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className={`rounded px-1.5 py-0.5 text-xs ${REGIME_COLORS_STATIC[e.regime] || ""}`}>
            {isRu ? (REGIME_RU_STATIC[e.regime] || e.regime) : (e.regime || "").replace("_", " ")}
          </span>
          {!e.regime_compatible && (
            <span className="rounded bg-red-500/10 px-1.5 py-0.5 text-xs text-red-400">!</span>
          )}
          <div className="w-12 text-right">
            <p className={`text-sm font-bold ${e.meta_score >= 0.6 ? "text-green-400" : e.meta_score >= 0.4 ? "text-yellow-400" : "text-red-400"}`}>
              {(e.meta_score * 100).toFixed(0)}%
            </p>
          </div>
          <span className={`rounded-md px-2 py-1 text-xs font-bold ${REC_COLORS_STATIC[e.recommendation] || ""}`}>
            {isRu ? e.recommendation_ru : (e.recommendation || "").replace("_", " ")}
          </span>
        </div>
      </div>
    </div>
  );
}
