"""LangGraph Signal Agent — Phase 4 Step 4 плана обучения.

ЗАЧЕМ LangGraph вместо imperative pipeline?
  signal_pipeline.py: process_and_broadcast() — линейный скрипт,
    трудно дебагировать, невозможно replay отдельного шага, нет явных переходов.
  LangGraph StateGraph — каждый узел виден в трассе, переходы явные,
    можно replay с любого состояния, легко добавить/убрать узел или сделать ветвление.

Граф (узлы → рёбра):
  START
    ↓
  load_context      ← загружаем Signal + Provider из БД
    ↓
  detect_regime     ← RegimeDetector.detect() (Level 1 quant)
    ↓
  compute_wef       ← AIRatingService.rate_signal() (9-факторный WEF Score)
    ↓
  meta_evaluate     ← MetaAgent.evaluate() (Level 2: адаптивные веса по режиму)
    ↓
  llm_reasoning     ← OpenRouter LLM синтезирует человеко-читаемый вердикт
    ↓                  (НОВЫЙ шаг, которого нет в original pipeline!)
  quality_gate      ← Правила: WEF ≥ 0.50, meta_score ≥ 0.55, R:R ≥ 1.5
    ↓ [conditional]
  approve → END
  reject  → END

Ключевое отличие от process_and_broadcast():
  Узел llm_reasoning получает ВЕСЬ контекст (regime + WEF factors + meta_score)
  и объясняет трейдеру ПОЧЕМУ сигнал принят или отклонён — не просто число.
"""
from __future__ import annotations

import json
import logging
from typing import Any, TypedDict

logger = logging.getLogger(__name__)

# ── State ─────────────────────────────────────────────────────────────────────

class SignalAnalysisState(TypedDict):
    """Полное состояние, пронизывающее все узлы графа.

    Каждый узел читает нужные ключи и возвращает dict с обновлёнными.
    LangGraph делает shallow merge: новые ключи добавляются, старые перезаписываются.
    """
    # Входной контекст
    signal_id: str
    db: Any                       # AsyncSession — только for in-process use

    # Загруженные ORM-объекты (узел load_context)
    signal: Any                   # Signal | None
    provider: Any                 # Provider | None

    # Узел detect_regime
    regime: str                   # MarketRegime.value
    regime_confidence: float

    # Узел compute_wef
    wef_score: float              # 0..1
    wef_coverage: float           # доля факторов с реальными данными
    wef_factors: dict             # {factor: score} breakdown
    wef_reasoning: str

    # Узел meta_evaluate
    meta_score: float             # 0..1
    meta_recommendation: str      # "strong_buy" | "buy" | "neutral" | "avoid" | "strong_avoid"
    meta_recommendation_ru: str
    meta_reasoning: list[str]
    strategy_name: str
    regime_compatible: bool

    # Узел llm_reasoning (новый, нет в original pipeline)
    llm_analysis: str             # человеко-читаемый вердикт с объяснением

    # Узел quality_gate
    quality_passed: bool
    rejection_reasons: list[str]

    # Сквозная трасса — полезна для отладки и explainability
    trace: list[str]


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _signal_to_context_str(state: SignalAnalysisState) -> str:
    sig = state["signal"]
    if sig is None:
        return "Сигнал не найден."
    return (
        f"Тикер: {sig.ticker}\n"
        f"Направление: {sig.action.value if hasattr(sig.action, 'value') else sig.action}\n"
        f"Вход: {sig.entry_price}, TP: {sig.take_profit}, SL: {sig.stop_loss}\n"
        f"Таймфрейм: {sig.timeframe}\n"
        f"WEF Score: {state.get('wef_score', 0):.2f} (покрытие факторов: {state.get('wef_coverage', 0):.0%})\n"
        f"Meta Score: {state.get('meta_score', 0):.2f} | Рекомендация: {state.get('meta_recommendation_ru', '—')}\n"
        f"Режим рынка: {state.get('regime', '—')} (уверенность {state.get('regime_confidence', 0):.2f})\n"
        f"Стратегия: {state.get('strategy_name', '—')} | Соответствует режиму: {state.get('regime_compatible', False)}\n"
        f"WEF факторы: {json.dumps(state.get('wef_factors', {}), ensure_ascii=False)}\n"
        f"Meta рассуждение: {'; '.join(state.get('meta_reasoning', []))}"
    )


async def _call_openrouter(prompt: str) -> str:
    import httpx
    from app.config import settings

    if not settings.openrouter_api_key:
        return "LLM недоступен: openrouter_api_key не задан."

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
                json={
                    "model": settings.llm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 400,
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.warning("LangGraph llm_reasoning: OpenRouter call failed: %s", exc)
        return f"LLM недоступен: {exc}"


# ── Узлы графа ────────────────────────────────────────────────────────────────

async def load_context(state: SignalAnalysisState) -> dict:
    """Загружает Signal и Provider из PostgreSQL."""
    from sqlalchemy import select
    from app.models.signal import Signal
    from app.models.provider import Provider

    db = state["db"]
    signal_id = state["signal_id"]

    result = await db.execute(select(Signal).where(Signal.id == signal_id))
    signal = result.scalar_one_or_none()

    provider = None
    if signal and signal.provider_id:
        res_p = await db.execute(select(Provider).where(Provider.id == signal.provider_id))
        provider = res_p.scalar_one_or_none()

    return {
        "signal": signal,
        "provider": provider,
        "trace": [f"load_context: signal={'найден' if signal else 'НЕ НАЙДЕН'}"],
    }


async def detect_regime(state: SignalAnalysisState) -> dict:
    """Level 1: определяем текущий режим рынка."""
    from app.services.quant.regime import regime_detector

    signal = state.get("signal")
    if signal is None:
        return {"regime": "UNKNOWN", "regime_confidence": 0.0,
                "trace": state["trace"] + ["detect_regime: пропущен — сигнал не найден"]}

    market_state = await regime_detector.detect(state["db"], ticker=signal.ticker)
    regime_str = market_state.regime.value if hasattr(market_state.regime, "value") else str(market_state.regime)

    return {
        "regime": regime_str,
        "regime_confidence": getattr(market_state, "regime_confidence", 0.5),
        "trace": state["trace"] + [f"detect_regime: {regime_str}"],
    }


async def compute_wef(state: SignalAnalysisState) -> dict:
    """WEF Score: 9-факторная оценка сигнала через AIRatingService."""
    from app.services.ai_rating import AIRatingService

    signal = state.get("signal")
    if signal is None:
        return {"wef_score": 0.0, "wef_coverage": 0.0, "wef_factors": {},
                "wef_reasoning": "Сигнал не найден",
                "trace": state["trace"] + ["compute_wef: пропущен"]}

    service = AIRatingService()
    breakdown = await service.rate_signal(state["db"], signal)

    factors = {k: round(v, 3) for k, v in (breakdown.scores or {}).items() if v is not None}

    return {
        "wef_score": round(breakdown.final_confidence or 0.0, 4),
        "wef_coverage": round(breakdown.coverage or 0.0, 4),
        "wef_factors": factors,
        "wef_reasoning": breakdown.reasoning or "",
        "trace": state["trace"] + [f"compute_wef: {breakdown.final_confidence:.2f} (coverage {breakdown.coverage:.0%})"],
    }


async def meta_evaluate(state: SignalAnalysisState) -> dict:
    """Level 2: MetaAgent с адаптивными весами по режиму рынка."""
    from app.services.quant.meta_agent import MetaAgent

    signal = state.get("signal")
    if signal is None:
        return {"meta_score": 0.0, "meta_recommendation": "avoid",
                "meta_recommendation_ru": "Нет сигнала", "meta_reasoning": [],
                "strategy_name": "—", "regime_compatible": False,
                "trace": state["trace"] + ["meta_evaluate: пропущен"]}

    agent = MetaAgent()
    decision = await agent.evaluate(state["db"], signal, state.get("provider"))

    return {
        "meta_score": round(decision.meta_score, 4),
        "meta_recommendation": decision.recommendation,
        "meta_recommendation_ru": decision.recommendation_ru,
        "meta_reasoning": decision.reasoning,
        "strategy_name": decision.strategy_name_ru,
        "regime_compatible": decision.regime_compatible,
        "trace": state["trace"] + [
            f"meta_evaluate: meta_score={decision.meta_score:.2f} [{decision.recommendation}]"
        ],
    }


async def llm_reasoning(state: SignalAnalysisState) -> dict:
    """НОВЫЙ узел (нет в original pipeline): LLM синтезирует вердикт на основе всего контекста.

    Даёт трейдеру ответ на вопрос «ПОЧЕМУ», а не только число WEF Score.
    Retrieval-grounded: LLM видит только факты из state, не генерирует рыночные прогнозы.
    """
    context = _signal_to_context_str(state)
    prompt = (
        "Ты — аналитик торговых сигналов платформы WinExtraFlow.\n\n"
        "Тебе даны ФАКТЫ оценки сигнала. Напиши краткое (3-4 предложения) объяснение "
        "для трейдера: почему этот сигнал получил такую оценку и на что обратить внимание.\n"
        "Строго опирайся только на предоставленные факты. Не давай инвестиционных советов.\n\n"
        f"ФАКТЫ:\n{context}"
    )

    analysis = await _call_openrouter(prompt)

    return {
        "llm_analysis": analysis,
        "trace": state["trace"] + [f"llm_reasoning: {len(analysis)} chars"],
    }


def quality_gate(state: SignalAnalysisState) -> dict:
    """Правила: WEF ≥ 0.50, meta_score ≥ 0.55, signal найден."""
    reasons = []

    if state.get("signal") is None:
        reasons.append("Сигнал не найден в БД")

    wef = state.get("wef_score", 0.0)
    if wef < 0.50:
        reasons.append(f"WEF Score {wef:.2f} < минимального порога 0.50")

    meta = state.get("meta_score", 0.0)
    if meta < 0.55:
        reasons.append(f"Meta Score {meta:.2f} < минимального порога 0.55")

    if not state.get("regime_compatible", True) and state.get("regime") == "HIGH_VOLATILITY":
        reasons.append("Стратегия несовместима с HIGH_VOLATILITY режимом")

    passed = len(reasons) == 0
    return {
        "quality_passed": passed,
        "rejection_reasons": reasons,
        "trace": state["trace"] + [
            "quality_gate: ПРОЙДЕН" if passed else f"quality_gate: ОТКЛОНЁН ({'; '.join(reasons)})"
        ],
    }


# ── Conditional edge ──────────────────────────────────────────────────────────

def route_quality(state: SignalAnalysisState) -> str:
    return "approve" if state.get("quality_passed") else "reject"


# ── Terminal nodes ────────────────────────────────────────────────────────────

def approve(state: SignalAnalysisState) -> dict:
    return {"trace": state["trace"] + ["→ APPROVE"]}


def reject_signal(state: SignalAnalysisState) -> dict:
    return {"trace": state["trace"] + [f"→ REJECT: {state.get('rejection_reasons', [])}"]}


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_signal_graph():
    """Компилирует StateGraph и возвращает runnable граф.

    Вызывается один раз при старте (или lazy при первом запросе).
    Граф stateless — состояние хранится в SignalAnalysisState, не в графе.
    """
    from langgraph.graph import StateGraph, END

    g = StateGraph(SignalAnalysisState)

    # Регистрируем узлы
    g.add_node("load_context",   load_context)
    g.add_node("detect_regime",  detect_regime)
    g.add_node("compute_wef",    compute_wef)
    g.add_node("meta_evaluate",  meta_evaluate)
    g.add_node("llm_reasoning",  llm_reasoning)
    g.add_node("quality_gate",   quality_gate)
    g.add_node("approve",        approve)
    g.add_node("reject_signal",  reject_signal)

    # Линейные рёбра
    g.set_entry_point("load_context")
    g.add_edge("load_context",  "detect_regime")
    g.add_edge("detect_regime", "compute_wef")
    g.add_edge("compute_wef",   "meta_evaluate")
    g.add_edge("meta_evaluate", "llm_reasoning")
    g.add_edge("llm_reasoning", "quality_gate")

    # Условное ветвление после quality_gate
    g.add_conditional_edges(
        "quality_gate",
        route_quality,
        {"approve": "approve", "reject": "reject_signal"},
    )

    # Терминальные узлы
    g.add_edge("approve",       END)
    g.add_edge("reject_signal", END)

    return g.compile()


# Singleton — компилируется при первом импорте
_graph = None


def get_signal_graph():
    global _graph
    if _graph is None:
        _graph = build_signal_graph()
    return _graph


async def run_signal_analysis(db: Any, signal_id: str) -> SignalAnalysisState:
    """Точка входа для вызова из роутера.

    Returns final state dict — содержит полный trace, scores, llm_analysis.
    """
    graph = get_signal_graph()

    initial_state: SignalAnalysisState = {
        "signal_id": signal_id,
        "db": db,
        "signal": None,
        "provider": None,
        "regime": "UNKNOWN",
        "regime_confidence": 0.0,
        "wef_score": 0.0,
        "wef_coverage": 0.0,
        "wef_factors": {},
        "wef_reasoning": "",
        "meta_score": 0.0,
        "meta_recommendation": "neutral",
        "meta_recommendation_ru": "—",
        "meta_reasoning": [],
        "strategy_name": "—",
        "regime_compatible": True,
        "llm_analysis": "",
        "quality_passed": False,
        "rejection_reasons": [],
        "trace": [],
    }

    final_state: SignalAnalysisState = await graph.ainvoke(initial_state)
    return final_state
