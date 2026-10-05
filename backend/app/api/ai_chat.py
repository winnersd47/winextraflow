"""AI Chat — assistant for signal analysis.

Retrieval-grounded: this module pulls the facts out of the database, then
services/ai_assistant.py has the LLM turn them into an answer. When the LLM is
unavailable the templated answer built here is returned instead, so the endpoint
degrades rather than fails.

The facts are subject to the same discipline as the public track record: seed and
test rows are excluded, and no win rate or average return is reported below
MIN_SAMPLE closed trades. Before that rule was applied here, a single closed trade
on a ticker made this endpoint answer "Win Rate: 100%".
"""

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.track_record import MIN_SAMPLE
from app.database import get_db
from app.models.signal import Signal, SignalAction, SignalStatus
from app.models.provider import Provider
from app.models.user import User
from app.services.ai_assistant import compose
from app.services.signal_quality import is_seed_signal

logger = logging.getLogger(__name__)
router = APIRouter()

DISCLAIMER = ("\n\n⚠️ Не является инвестиционной рекомендацией. "
              "Все решения принимаются пользователем самостоятельно.")

REGIME_RU = {
    "trending_up": "Тренд вверх",
    "trending_down": "Тренд вниз",
    "ranging": "Боковик",
    "high_volatility": "Высокая волатильность",
    "low_volatility": "Низкая волатильность",
    "breakout": "Пробой",
    "unknown": "Не определён",
}


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    answer: str
    signals_referenced: int = 0
    disclaimer: bool = True
    # True when the LLM composed the answer, False when the template did. Exposed
    # so the UI can label it and so a silent LLM outage is visible in logs.
    llm: bool = False


def _not_seed_sql():
    """SQL-level exclusion of seed/test rows, for use before a LIMIT."""
    from sqlalchemy import and_, or_
    from app.services.signal_quality import SEED_MARKERS, TEST_TICKERS
    return and_(
        Signal.ticker.notin_(TEST_TICKERS),
        or_(Signal.raw_message.is_(None),
            and_(*[Signal.raw_message.notlike(f"{m}%") for m in SEED_MARKERS])),
    )


async def _answer(question: str, facts: dict, fallback: str, referenced: int) -> ChatResponse:
    """Compose with the LLM, fall back to the template, always disclaim."""
    text = await compose(question, facts)
    return ChatResponse(
        answer=(text or fallback).rstrip() + DISCLAIMER,
        signals_referenced=referenced,
        llm=bool(text),
    )


@router.post("/ask", response_model=ChatResponse)
async def ai_chat_ask(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """AI assistant answers questions about tickers and signals."""
    msg = req.message.strip().lower()
    if len(msg) < 2:
        raise HTTPException(400, "Message too short")
    if len(req.message) > 500:
        raise HTTPException(400, "Message too long (max 500)")

    # Extract ticker from message
    ticker = _extract_ticker(msg)

    if ticker:
        return await _analyze_ticker(ticker, req.message, db)
    # Providers before signals: "лучшие провайдеры" matches both, and the signals
    # branch used to win, so the provider question was never actually answered.
    elif any(w in msg for w in ["провайдер", "provider", "лидер", "leader"]):
        return await _best_providers(req.message, db)
    elif any(w in msg for w in ["режим", "regime", "рынок", "market"]):
        return await _market_overview(req.message, db)
    elif any(w in msg for w in ["лучш", "best", "топ", "top", "рекоменд"]):
        return await _best_signals(req.message, db)
    else:
        return await _general_help(msg, db)


def _extract_ticker(msg: str) -> str | None:
    """Try to extract a ticker symbol from the message."""
    # Known tickers
    KNOWN = [
        "SBER", "GAZP", "LKOH", "YNDX", "ROSN", "GMKN", "NVTK", "MGNT",
        "VTBR", "MTSS", "POLY", "FIVE", "OZON", "TCSG", "PHOR", "NLMK",
        "CHMF", "ALRS", "AFLT", "MOEX", "PLZL", "RUAL", "SNGS", "TATN",
        "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
        "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOG", "META",
    ]
    msg_upper = msg.upper()
    for t in KNOWN:
        if t in msg_upper:
            return t
    # Try to find a word that looks like a ticker (3-6 uppercase letters)
    import re
    matches = re.findall(r'\b([A-ZА-Я]{3,8})\b', msg.upper())
    for m in matches:
        if m in KNOWN:
            return m
    return None


async def _analyze_ticker(ticker: str, question: str, db: AsyncSession) -> ChatResponse:
    """Analyze a specific ticker based on platform signals."""
    # Get recent signals for this ticker
    week_ago = datetime.now(timezone.utc) - timedelta(days=30)
    stmt = (
        select(Signal)
        .where(Signal.ticker == ticker, Signal.created_at >= week_ago)
        .order_by(Signal.created_at.desc())
        .limit(20)
    )
    signals = (await db.execute(stmt)).scalars().all()
    # Seed and stress-test rows outnumber real signals in this table; counted here
    # they would be presented to the user as this ticker's real history.
    signals = [s for s in signals if not is_seed_signal(s)]

    if not signals:
        return ChatResponse(
            answer=f"По тикеру {ticker} нет сигналов за последние 30 дней. "
                   f"Следите за обновлениями — новые сигналы появляются ежедневно.\n\n"
                   f"Попробуйте добавить провайдера, который работает с {ticker}."
                   + DISCLAIMER,
            signals_referenced=0,
        )

    # Analyze
    total = len(signals)
    buys = sum(1 for s in signals if s.action == SignalAction.BUY)
    sells = total - buys
    avg_confidence = sum(s.ai_confidence or 0 for s in signals) / total if total else 0
    active = sum(1 for s in signals if s.status == SignalStatus.ACTIVE)

    # Closed signals stats. A ratio over a handful of trades is noise, so it is not
    # reported at all below MIN_SAMPLE — the same threshold the public track record
    # uses. One closed trade used to produce "Win Rate: 100%" here.
    closed = [s for s in signals if s.profit_pct is not None]
    enough = len(closed) >= MIN_SAMPLE
    wins = sum(1 for s in closed if s.profit_pct > 0)
    win_rate = wins / len(closed) * 100 if enough else None
    avg_profit = sum(s.profit_pct for s in closed) / len(closed) if enough else None

    # Latest signal
    latest = signals[0]
    latest_action = "ПОКУПКА" if latest.action == SignalAction.BUY else "ПРОДАЖА"

    # WEF Score interpretation
    if avg_confidence >= 0.8:
        score_text = "Отличный (80%+)"
    elif avg_confidence >= 0.6:
        score_text = "Хороший (60-80%)"
    elif avg_confidence >= 0.4:
        score_text = "Средний (40-60%)"
    else:
        score_text = "Низкий (<40%)"

    # Build bias
    if buys > sells * 2:
        bias = "сильный бычий уклон"
    elif buys > sells:
        bias = "умеренный бычий уклон"
    elif sells > buys * 2:
        bias = "сильный медвежий уклон"
    elif sells > buys:
        bias = "умеренный медвежий уклон"
    else:
        bias = "нейтральный (равное количество BUY/SELL)"

    answer = (
        f"**Анализ {ticker}** (последние 30 дней)\n\n"
        f"Сигналов: {total} (BUY: {buys}, SELL: {sells}) — {bias}\n"
        f"WEF Score (средний): {avg_confidence:.0%} — {score_text}\n"
        f"Активных: {active}\n"
    )

    if enough:
        answer += (
            f"\nЗакрытых: {len(closed)} | Win Rate: {win_rate:.0f}% | "
            f"Средняя прибыль: {avg_profit:+.1f}%\n"
        )
    elif closed:
        answer += (
            f"\nЗакрытых сделок: {len(closed)} — этого мало для статистики. "
            f"Win rate и доходность показываем от {MIN_SAMPLE} сделок.\n"
        )

    answer += (
        f"\nПоследний сигнал: {latest_action} по {latest.entry_price}"
    )
    if latest.take_profit:
        answer += f" | TP: {latest.take_profit}"
    if latest.stop_loss:
        answer += f" | SL: {latest.stop_loss}"
    if latest.long_target:
        answer += f"\nДолгосрочный ориентир источника: {latest.long_target:g}"

    if latest.ai_reasoning:
        answer += f"\nAI: {latest.ai_reasoning}"

    facts = {
        "тикер": ticker,
        "период": "последние 30 дней",
        "сигналов_всего": total, "buy": buys, "sell": sells, "уклон": bias,
        "средний_wef_score_pct": round(avg_confidence * 100),
        "интерпретация_wef": score_text,
        "активных_сигналов": active,
        "закрытых_сделок": len(closed),
        "enough_data": enough,
        "статистика_достоверна": ("да" if enough else
                                  f"НЕТ — закрытых сделок {len(closed)}, "
                                  f"нужно минимум {MIN_SAMPLE}"),
        "min_sample": MIN_SAMPLE,
        "win_rate_pct": round(win_rate, 1) if win_rate is not None else None,
        "средний_результат_pct": round(avg_profit, 2) if avg_profit is not None else None,
        "последний_сигнал": {
            "действие": latest_action,
            "вход": latest.entry_price,
            "цель": latest.take_profit,
            "стоп": latest.stop_loss,
            "долгосрочный_ориентир": latest.long_target,
            "wef_score_pct": round((latest.ai_confidence or 0) * 100) or None,
            "обоснование": latest.ai_reasoning,
        },
    }
    return await _answer(question, facts, answer, total)


async def _market_overview(question: str, db: AsyncSession) -> ChatResponse:
    """General market overview."""
    from app.services.quant.regime import regime_detector

    # RegimeDetector exposes `detect(db)` and returns a MarketStateVector. The old
    # call here was `detect_regime()` — a method that does not exist — so every
    # "режим рынка" question answered with a 500.
    state = await regime_detector.detect(db)

    # Count signals by action in last 7 days
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    stmt = select(Signal).where(Signal.created_at >= week_ago)
    signals = [s for s in (await db.execute(stmt)).scalars().all()
               if not is_seed_signal(s)]

    buys = sum(1 for s in signals if s.action == SignalAction.BUY)
    sells = len(signals) - buys

    regime_ru = REGIME_RU.get(state.regime.value, state.regime.value)
    balance = ("бычий перевес" if buys > sells
               else "медвежий перевес" if sells > buys else "баланс")
    answer = (
        f"**Обзор рынка**\n\n"
        f"Текущий режим: {regime_ru}\n"
        f"Уверенность режима: {state.confidence:.0%}\n\n"
        f"За последние 7 дней: {len(signals)} сигналов (BUY: {buys}, SELL: {sells})\n"
        f"Соотношение: {balance}"
    )

    facts = {
        "режим_рынка": regime_ru,
        "уверенность_режима_pct": round(state.confidence * 100),
        "доля_buy_pct": round(state.buy_ratio * 100),
        "период": "последние 7 дней",
        "сигналов": len(signals), "buy": buys, "sell": sells, "перевес": balance,
        "примечание": "Режим определяется по потоку сигналов платформы, "
                      "а не по внешним рыночным данным.",
    }
    return await _answer(question, facts, answer, len(signals))


async def _best_signals(question: str, db: AsyncSession) -> ChatResponse:
    """Top signals by WEF Score."""
    # Seed rows must be excluded in SQL, not after the LIMIT: they outnumber real
    # signals and carry high scores, so an ordered top-15 was entirely demo data and
    # the filter left nothing — the endpoint answered "нет сигналов" with 5 live.
    stmt = (
        select(Signal)
        .where(Signal.status == SignalStatus.ACTIVE,
               Signal.ai_confidence.isnot(None),
               _not_seed_sql())
        .order_by(Signal.ai_confidence.desc())
        .limit(15)
    )
    rows = [s for s in (await db.execute(stmt)).scalars().all() if not is_seed_signal(s)]
    signals = rows[:5]

    if not signals:
        return ChatResponse(answer="Нет активных сигналов с AI-оценкой." + DISCLAIMER,
                            signals_referenced=0)

    lines = ["**Топ-5 активных сигналов по WEF Score**\n"]
    for i, s in enumerate(signals, 1):
        action = "BUY" if s.action == SignalAction.BUY else "SELL"
        lines.append(
            f"{i}. **{s.ticker}** {action} — WEF {s.ai_confidence:.0%} | "
            f"Entry: {s.entry_price}"
        )

    facts = {
        "сортировка": "по WEF Score, убывание",
        "сигналы": [
            {"тикер": s.ticker,
             "действие": "BUY" if s.action == SignalAction.BUY else "SELL",
             "wef_score_pct": round((s.ai_confidence or 0) * 100),
             "вход": s.entry_price, "цель": s.take_profit, "стоп": s.stop_loss}
            for s in signals
        ],
        "примечание": "WEF Score оценивает качество входных данных сигнала; "
                      "он ещё не подтверждён статистикой исходов.",
    }
    return await _answer(question, facts, "\n".join(lines), len(signals))


async def _best_providers(question: str, db: AsyncSession) -> ChatResponse:
    """Top providers by performance.

    Requires a real sample: ordering by win_rate alone put a provider with two
    lucky trades above one with a hundred measured ones.
    """
    stmt = (
        select(Provider)
        .where(Provider.is_seed.is_(False),
               Provider.win_rate.isnot(None),
               Provider.total_signals >= MIN_SAMPLE)
        .order_by(Provider.win_rate.desc())
        .limit(5)
    )
    providers = (await db.execute(stmt)).scalars().all()

    if not providers:
        total = (await db.execute(select(func.count(Provider.id)).where(
            Provider.is_seed.is_(False)))).scalar() or 0
        answer = (
            f"Ни у одного провайдера пока нет измеренной статистики: нужно минимум "
            f"{MIN_SAMPLE} закрытых сделок, прежде чем показывать win rate. "
            f"Реальных провайдеров на платформе: {total}."
        )
        facts = {"провайдеров_всего": total, "min_sample": MIN_SAMPLE,
                 "enough_data": False,
                 "статистика_достоверна": f"НЕТ — ни у кого нет {MIN_SAMPLE} сделок"}
        return await _answer(question, facts, answer, 0)

    lines = [f"**Топ-5 провайдеров по Win Rate** (от {MIN_SAMPLE} сигналов)\n"]
    for i, p in enumerate(providers, 1):
        wr = f"{p.win_rate * 100:.0f}%" if p.win_rate else "N/A"
        sharpe = f"{p.sharpe_ratio:.1f}" if p.sharpe_ratio else "N/A"
        lines.append(
            f"{i}. **{p.name}** — WR: {wr} | Sharpe: {sharpe} | "
            f"Сигналов: {p.total_signals}"
        )

    facts = {
        "min_sample": MIN_SAMPLE, "enough_data": True,
        "статистика_достоверна": "да",
        "провайдеры": [
            {"название": p.name,
             "win_rate_pct": round((p.win_rate or 0) * 100),
             "sharpe": round(p.sharpe_ratio, 2) if p.sharpe_ratio else None,
             "сигналов": p.total_signals}
            for p in providers
        ],
    }
    return await _answer(question, facts, "\n".join(lines), 0)


async def _general_help(msg: str, db: AsyncSession) -> ChatResponse:
    """General help response."""
    # Count platform stats
    total_signals = (await db.execute(select(func.count(Signal.id)))).scalar() or 0

    answer = (
        "**WinExtraFlow AI Assistant**\n\n"
        "Я могу помочь с:\n"
        "- **Анализ тикера** — напишите тикер (SBER, BTCUSDT, AAPL)\n"
        "- **Обзор рынка** — спросите 'режим рынка' или 'market overview'\n"
        "- **Лучшие сигналы** — спросите 'топ сигналы' или 'best signals'\n"
        "- **Лучшие провайдеры** — спросите 'лучшие провайдеры'\n\n"
        f"На платформе {total_signals} сигналов.\n\n"
        "Примеры:\n"
        "• 'Стоит ли покупать SBER?'\n"
        "• 'Анализ BTCUSDT'\n"
        "• 'Какой сейчас режим рынка?'\n"
        "• 'Покажи лучшие сигналы'"
        + DISCLAIMER
    )

    return ChatResponse(answer=answer, signals_referenced=0)
