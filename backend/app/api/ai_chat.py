"""AI Chat — intelligent assistant for signal analysis.

Answers questions about tickers, signals, market regime using platform data.
Does NOT use external LLM — uses rule-based analysis from evolutionary components.
"""

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.signal import Signal, SignalAction, SignalStatus
from app.models.provider import Provider
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    answer: str
    signals_referenced: int = 0
    disclaimer: bool = True


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
        return await _analyze_ticker(ticker, msg, db)
    elif any(w in msg for w in ["режим", "regime", "рынок", "market"]):
        return await _market_overview(db)
    elif any(w in msg for w in ["лучш", "best", "топ", "top", "рекоменд"]):
        return await _best_signals(db)
    elif any(w in msg for w in ["провайдер", "provider", "лидер", "leader"]):
        return await _best_providers(db)
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


async def _analyze_ticker(ticker: str, msg: str, db: AsyncSession) -> ChatResponse:
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

    if not signals:
        return ChatResponse(
            answer=f"По тикеру {ticker} нет сигналов за последние 30 дней. "
                   f"Следите за обновлениями — новые сигналы появляются ежедневно.\n\n"
                   f"Попробуйте добавить провайдера, который работает с {ticker}.",
            signals_referenced=0,
        )

    # Analyze
    total = len(signals)
    buys = sum(1 for s in signals if s.action == SignalAction.BUY)
    sells = total - buys
    avg_confidence = sum(s.ai_confidence or 0 for s in signals) / total if total else 0
    active = sum(1 for s in signals if s.status == SignalStatus.ACTIVE)

    # Closed signals stats
    closed = [s for s in signals if s.profit_pct is not None]
    wins = sum(1 for s in closed if s.profit_pct > 0)
    win_rate = wins / len(closed) * 100 if closed else 0
    avg_profit = sum(s.profit_pct for s in closed) / len(closed) if closed else 0

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

    if closed:
        answer += (
            f"\nЗакрытых: {len(closed)} | Win Rate: {win_rate:.0f}% | "
            f"Средняя прибыль: {avg_profit:+.1f}%\n"
        )

    answer += (
        f"\nПоследний сигнал: {latest_action} по {latest.entry_price}"
    )
    if latest.take_profit:
        answer += f" | TP: {latest.take_profit}"
    if latest.stop_loss:
        answer += f" | SL: {latest.stop_loss}"

    if latest.ai_reasoning:
        answer += f"\nAI: {latest.ai_reasoning}"

    answer += (
        "\n\n⚠️ Не является инвестиционной рекомендацией. "
        "Все решения принимаются пользователем самостоятельно."
    )

    return ChatResponse(answer=answer, signals_referenced=total)


async def _market_overview(db: AsyncSession) -> ChatResponse:
    """General market overview."""
    from app.services.quant.regime import regime_detector

    regime = regime_detector.detect_regime()

    # Count signals by action in last 7 days
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    stmt = select(Signal).where(Signal.created_at >= week_ago)
    signals = (await db.execute(stmt)).scalars().all()

    buys = sum(1 for s in signals if s.action == SignalAction.BUY)
    sells = len(signals) - buys

    regime_ru = {
        "trending_up": "Тренд вверх",
        "trending_down": "Тренд вниз",
        "ranging": "Боковик",
        "high_volatility": "Высокая волатильность",
        "breakout": "Пробой",
    }.get(regime.get("regime", ""), regime.get("regime", "unknown"))

    answer = (
        f"**Обзор рынка**\n\n"
        f"Текущий режим: {regime_ru}\n"
        f"Уверенность режима: {regime.get('confidence', 0):.0%}\n\n"
        f"За последние 7 дней: {len(signals)} сигналов (BUY: {buys}, SELL: {sells})\n"
        f"Соотношение: {'бычий перевес' if buys > sells else 'медвежий перевес' if sells > buys else 'баланс'}\n\n"
        f"⚠️ Не является инвестиционной рекомендацией."
    )

    return ChatResponse(answer=answer, signals_referenced=len(signals))


async def _best_signals(db: AsyncSession) -> ChatResponse:
    """Top signals by WEF Score."""
    stmt = (
        select(Signal)
        .where(Signal.status == SignalStatus.ACTIVE, Signal.ai_confidence.isnot(None))
        .order_by(Signal.ai_confidence.desc())
        .limit(5)
    )
    signals = (await db.execute(stmt)).scalars().all()

    if not signals:
        return ChatResponse(answer="Нет активных сигналов с AI-оценкой.", signals_referenced=0)

    lines = ["**Топ-5 активных сигналов по WEF Score**\n"]
    for i, s in enumerate(signals, 1):
        action = "BUY" if s.action == SignalAction.BUY else "SELL"
        lines.append(
            f"{i}. **{s.ticker}** {action} — WEF {s.ai_confidence:.0%} | "
            f"Entry: {s.entry_price}"
        )

    lines.append("\n⚠️ Не является инвестиционной рекомендацией.")
    return ChatResponse(answer="\n".join(lines), signals_referenced=len(signals))


async def _best_providers(db: AsyncSession) -> ChatResponse:
    """Top providers by performance."""
    stmt = (
        select(Provider)
        .where(Provider.win_rate.isnot(None))
        .order_by(Provider.win_rate.desc())
        .limit(5)
    )
    providers = (await db.execute(stmt)).scalars().all()

    if not providers:
        return ChatResponse(answer="Нет провайдеров с историей.", signals_referenced=0)

    lines = ["**Топ-5 провайдеров по Win Rate**\n"]
    for i, p in enumerate(providers, 1):
        wr = f"{p.win_rate * 100:.0f}%" if p.win_rate else "N/A"
        sharpe = f"{p.sharpe_ratio:.1f}" if p.sharpe_ratio else "N/A"
        lines.append(
            f"{i}. **{p.name}** — WR: {wr} | Sharpe: {sharpe} | "
            f"Сигналов: {p.total_signals}"
        )

    lines.append("\n⚠️ Рейтинги основаны на исторических данных.")
    return ChatResponse(answer="\n".join(lines), signals_referenced=0)


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
        "• 'Покажи лучшие сигналы'\n\n"
        "⚠️ Не является инвестиционной рекомендацией."
    )

    return ChatResponse(answer=answer, signals_referenced=0)
