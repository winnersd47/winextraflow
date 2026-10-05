"""AI insights per dashboard block.

One endpoint per block. Each gathers facts from the database, hands them to
services/ai_assistant.compose, and falls back to a plain template when the LLM is
unavailable. The pattern is deliberately identical everywhere: the facts are
assembled in Python where they can be checked, and the model only writes prose.

Every fact set carries `статистика_достоверна` so the model cannot present a ratio
built on three trades as a finding. Seed and test rows are excluded in SQL, before
any LIMIT — filtering after a LIMIT returns an empty page while demo rows fill the
window, which is how "нет активных сигналов" appeared with five of them live.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.track_record import MIN_SAMPLE
from app.database import get_db
from app.models.signal import Signal, SignalAction, SignalStatus
from app.models.user import User
from app.services.ai_assistant import compose
from app.services.signal_quality import SEED_MARKERS, TEST_TICKERS

logger = logging.getLogger(__name__)
router = APIRouter()

DISCLAIMER = ("\n\n⚠️ Не является инвестиционной рекомендацией. "
              "Все решения принимаются пользователем самостоятельно.")


class Insight(BaseModel):
    text: str
    llm: bool = False
    facts: dict = {}


def not_seed():
    """SQL-level exclusion of seed/demo/test signal rows."""
    return and_(
        Signal.ticker.notin_(TEST_TICKERS),
        or_(Signal.raw_message.is_(None),
            and_(*[Signal.raw_message.notlike(f"{m}%") for m in SEED_MARKERS])),
    )


async def _insight(question: str, facts: dict, fallback: str) -> Insight:
    text = await compose(question, facts)
    return Insight(text=(text or fallback).rstrip() + DISCLAIMER,
                   llm=bool(text), facts=facts)


@router.get("/dashboard", response_model=Insight)
async def dashboard_insight(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """What is on the platform right now, and what actually changed."""
    day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    active = (await db.execute(
        select(Signal).where(Signal.status == SignalStatus.ACTIVE, not_seed())
        .order_by(Signal.ai_confidence.desc().nullslast()).limit(10)
    )).scalars().all()

    new_24h = (await db.execute(select(func.count(Signal.id)).where(
        Signal.created_at >= day_ago, not_seed()))).scalar() or 0

    closed_week = (await db.execute(
        select(Signal).where(
            Signal.status.in_((SignalStatus.CLOSED_TP, SignalStatus.CLOSED_SL)),
            Signal.created_at >= week_ago, not_seed())
    )).scalars().all()

    closed_total = (await db.execute(select(func.count(Signal.id)).where(
        Signal.status.in_((SignalStatus.CLOSED_TP, SignalStatus.CLOSED_SL)),
        not_seed()))).scalar() or 0

    # Paper accounts: the platform's own measured record.
    from app.models.paper import PaperAccount
    from app.services.paper_trading import account_stats, platform_accounts
    accounts = (await db.execute(platform_accounts(select(PaperAccount)))).scalars().all()
    paper = [await account_stats(db, a) for a in accounts]

    enough = closed_total >= MIN_SAMPLE
    facts = {
        "активных_сигналов": len(active),
        "новых_за_24ч": new_24h,
        "закрыто_за_неделю": len(closed_week),
        "закрытых_всего": closed_total,
        "min_sample": MIN_SAMPLE,
        "enough_data": enough,
        "статистика_достоверна": ("да" if enough else
                                  f"НЕТ — закрытых сделок {closed_total}, "
                                  f"нужно минимум {MIN_SAMPLE}"),
        "топ_активных": [
            {"тикер": s.ticker,
             "действие": "BUY" if s.action == SignalAction.BUY else "SELL",
             "wef_score_pct": round((s.ai_confidence or 0) * 100),
             "вход": s.entry_price, "цель": s.take_profit, "стоп": s.stop_loss}
            for s in active[:5]
        ],
        "демо_счета": [
            {"название": p["account"], "открытых": p["open_trades"],
             "закрытых": p["closed_trades"],
             "pnl_денег": p["pnl_money"], "валюта": p["currency"]}
            for p in paper
        ],
    }

    lines = [
        "**Состояние платформы**", "",
        f"Активных сигналов: {len(active)}",
        f"Новых за 24 часа: {new_24h}",
        f"Закрыто за неделю: {len(closed_week)} (всего измеренных: {closed_total})",
    ]
    if not enough:
        lines.append(f"Агрегированную доходность не показываем до {MIN_SAMPLE} "
                     f"закрытых сделок.")
    if paper:
        lines += ["", "**Демо-счета**"]
        for p in paper:
            sym = "₽" if p["currency"] == "RUB" else "$"
            lines.append(f"• {p['account']}: открыто {p['open_trades']}, "
                         f"закрыто {p['closed_trades']}, "
                         f"P&L {p['pnl_money']:+.0f} {sym}")

    return await _insight(
        "Опиши коротко текущее состояние платформы: сколько сигналов, что "
        "закрылось, в каком состоянии демо-счета. Не давай советов.",
        facts, "\n".join(lines))


@router.get("/screener", response_model=Insight)
async def screener_insight(
    market: str = "all",
    min_wef_score: float = 0.0,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """What the current scan actually shows, and where it has no data."""
    from app.api.screener import scan_tickers

    scan = await scan_tickers(market=market, min_signals=1,
                              min_wef_score=min_wef_score, action="all",
                              sort_by="wef_score", db=db, user=user)
    items = scan["items"]

    by_market: dict[str, int] = {}
    for r in items:
        by_market[r["market"]] = by_market.get(r["market"], 0) + 1
    rated = [r for r in items if r["enough_data"]]

    facts = {
        "фильтр_рынка": market,
        "тикеров_с_сигналами": len(items),
        "по_рынкам": by_market,
        "тикеров_с_достоверной_статистикой": len(rated),
        "min_sample": MIN_SAMPLE,
        "enough_data": bool(rated),
        "статистика_достоверна": (
            "да" if rated else
            f"НЕТ — ни у одного тикера нет {MIN_SAMPLE} закрытых сделок, "
            f"поэтому win rate и доходность не рассчитаны"),
        "топ_по_wef": [
            {"тикер": r["ticker"], "рынок": r["market"],
             "сигналов": r["total_signals"], "активных": r["active"],
             "wef_score_pct": round(r["avg_wef_score"] * 100),
             "уклон": r["bias"], "закрытых_сделок": r["closed_trades"]}
            for r in items[:8]
        ],
    }

    if not items:
        fallback = (f"По фильтру «{market}» нет тикеров с сигналами за 30 дней.")
    else:
        lines = [f"**Скринер: {len(items)} тикеров с сигналами за 30 дней**", ""]
        for r in items[:8]:
            lines.append(f"• {r['ticker']} ({r['market']}) — WEF "
                         f"{r['avg_wef_score'] * 100:.0f}%, сигналов "
                         f"{r['total_signals']}, активных {r['active']}, "
                         f"уклон {r['bias']}")
        if not rated:
            lines += ["", f"Win rate ни по одному тикеру не рассчитан: нужно "
                          f"минимум {MIN_SAMPLE} закрытых сделок."]
        fallback = "\n".join(lines)

    return await _insight(
        f"Опиши результаты скринера по фильтру «{market}»: где сосредоточены "
        f"сигналы, по каким тикерам данных недостаточно. Не рекомендуй покупки.",
        facts, fallback)


@router.get("/portfolio", response_model=Insight)
async def portfolio_insight(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Concentration and sizing of the user's own open positions.

    The useful observation here is structural, not predictive: how much of the
    portfolio sits in one name, and whether position sizes bear any relation to
    each other. That needs no forecast, so it is something the facts can support.
    """
    from app.api.portfolio import portfolio_summary

    p = await portfolio_summary(db=db, user=user)
    alloc = p["allocation"]
    positions = p["positions"]

    largest = max(alloc.items(), key=lambda kv: kv[1], default=(None, 0))
    over_25 = {t: v for t, v in alloc.items() if v > 25}

    facts = {
        "открытых_позиций": p["open_positions"],
        "вложено_всего": p["total_invested"],
        "реализованный_pnl": p["total_realized_pnl"],
        "закрытых_сделок": p["total_trades"],
        "win_rate_pct": round(p["win_rate"] * 100, 1) if p["win_rate"] is not None else None,
        "статистика_достоверна": (
            "да" if (p["total_trades"] or 0) >= MIN_SAMPLE else
            f"НЕТ — закрытых сделок {p['total_trades']}, "
            f"для выводов о win rate нужно минимум {MIN_SAMPLE}"),
        "enough_data": (p["total_trades"] or 0) >= MIN_SAMPLE,
        "распределение_pct": alloc,
        "крупнейшая_позиция": {"тикер": largest[0], "доля_pct": largest[1]},
        "позиции_свыше_25pct": over_25,
        "позиции": [
            {"тикер": x["ticker"], "действие": x["action"],
             "вход": x["entry_price"], "объём": x["value"]}
            for x in positions[:10]
        ],
        "ориентир_риска": "1% депозита на сделку, не более 25% в одну позицию "
                          "(см. services/position_sizing.py)",
    }

    if not positions:
        fallback = ("Открытых позиций нет. Записи появляются здесь из журнала "
                    "сделок — добавьте сделку, чтобы увидеть распределение.")
    else:
        lines = [f"**Портфель: {len(positions)} открытых позиций**", "",
                 f"Вложено: {p['total_invested']:,.0f}".replace(",", " ")]
        if largest[0]:
            lines.append(f"Крупнейшая позиция: {largest[0]} — {largest[1]:.0f}% портфеля")
        if over_25:
            lines.append(f"Свыше 25% портфеля в одной позиции: "
                         f"{', '.join(f'{t} ({v:.0f}%)' for t, v in over_25.items())}")
        if p["total_trades"]:
            lines.append(f"Закрытых сделок: {p['total_trades']}, "
                         f"реализованный P&L: {p['total_realized_pnl']:+,.0f}"
                         .replace(",", " "))
        if (p["total_trades"] or 0) < MIN_SAMPLE:
            lines.append(f"Для выводов о win rate нужно минимум {MIN_SAMPLE} "
                         f"закрытых сделок.")
        fallback = "\n".join(lines)

    return await _insight(
        "Опиши структуру портфеля: концентрация, крупнейшие позиции, соответствие "
        "ориентиру риска. Не предлагай что покупать или продавать.",
        facts, fallback)


# A personal journal will never reach MIN_SAMPLE per emotion or tag, so groupings
# use a lower bar — and are labelled as indicative rather than statistical, which
# is the honest description of an average over five trades.
MIN_GROUP = 5


def _group_stats(entries: list, key) -> dict:
    """Average result per group, only for groups big enough to mention."""
    buckets: dict[str, list[float]] = {}
    for e in entries:
        for k in key(e):
            if k and e.profit_pct is not None:
                buckets.setdefault(str(k), []).append(e.profit_pct)
    return {
        k: {"сделок": len(v), "средний_результат_pct": round(sum(v) / len(v), 2)}
        for k, v in buckets.items() if len(v) >= MIN_GROUP
    }


@router.get("/journal", response_model=Insight)
async def journal_insight(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Patterns in the user's own trade journal.

    Behavioural, not predictive: how results differ by the emotion and tags the
    user recorded, and whether their own rating matched the outcome. All of it is
    description of their past entries, which is what the data can actually support.
    """
    from app.models.journal import JournalEntry

    entries = (await db.execute(
        select(JournalEntry).where(JournalEntry.user_id == str(user.id))
        .order_by(JournalEntry.opened_at.desc()).limit(500)
    )).scalars().all()
    closed = [e for e in entries if e.profit_pct is not None]

    by_emotion = _group_stats(closed, lambda e: [e.emotion])
    by_tag = _group_stats(closed, lambda e: (e.tags or []))

    # Did the user's own confidence match the outcome? Only with enough rated trades.
    rated = [e for e in closed if e.rating is not None]
    rating_split = {}
    if len(rated) >= MIN_GROUP * 2:
        high = [e.profit_pct for e in rated if e.rating >= 4]
        low = [e.profit_pct for e in rated if e.rating <= 2]
        if len(high) >= MIN_GROUP:
            rating_split["самооценка_4_5"] = {
                "сделок": len(high),
                "средний_результат_pct": round(sum(high) / len(high), 2)}
        if len(low) >= MIN_GROUP:
            rating_split["самооценка_1_2"] = {
                "сделок": len(low),
                "средний_результат_pct": round(sum(low) / len(low), 2)}

    wins = sum(1 for e in closed if (e.profit_pct or 0) > 0)
    facts = {
        "записей_всего": len(entries),
        "закрытых": len(closed),
        "открытых": len(entries) - len(closed),
        "в_плюс": wins,
        "min_group": MIN_GROUP,
        "enough_data": len(closed) >= MIN_SAMPLE,
        "статистика_достоверна": (
            "да" if len(closed) >= MIN_SAMPLE else
            f"НЕТ — закрытых сделок {len(closed)}. Разбивки ниже посчитаны от "
            f"{MIN_GROUP} сделок в группе и являются наблюдением, не статистикой"),
        "по_эмоции": by_emotion,
        "по_тегам": by_tag,
        "самооценка_против_результата": rating_split,
    }

    if not entries:
        fallback = ("Журнал пуст. Добавьте сделки — по эмоциям, тегам и вашей "
                    "самооценке появятся наблюдения о собственных решениях.")
    else:
        lines = [f"**Журнал: {len(entries)} записей, закрытых {len(closed)}**", ""]
        if by_emotion:
            lines.append("Средний результат по эмоции:")
            for k, v in sorted(by_emotion.items(),
                               key=lambda kv: kv[1]["средний_результат_pct"], reverse=True):
                lines.append(f"• {k}: {v['средний_результат_pct']:+.1f}% "
                             f"({v['сделок']} сделок)")
        if by_tag:
            lines.append("")
            lines.append("Средний результат по тегу:")
            for k, v in sorted(by_tag.items(),
                               key=lambda kv: kv[1]["средний_результат_pct"], reverse=True):
                lines.append(f"• {k}: {v['средний_результат_pct']:+.1f}% "
                             f"({v['сделок']} сделок)")
        if not by_emotion and not by_tag:
            lines.append(f"Для разбивок нужно минимум {MIN_GROUP} закрытых сделок "
                         f"в группе. Заполняйте эмоцию и теги — тогда появятся "
                         f"наблюдения о собственных решениях.")
        fallback = "\n".join(lines)

    return await _insight(
        "Опиши закономерности в журнале сделок пользователя: как результат "
        "различается по эмоции и тегам, совпадала ли его самооценка с исходом. "
        "Это наблюдения о его поведении, не прогноз. Советов не давай.",
        facts, fallback)


@router.get("/marketplace", response_model=Insight)
async def marketplace_insight(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """What the marketplace currently contains — including how much of it is demo."""
    from app.models.provider import Provider
    from app.models.strategy import Strategy

    rows = (await db.execute(
        select(Strategy, Provider).join(Provider, Strategy.provider_id == Provider.id)
        .where(Strategy.is_published.is_(True))
    )).all()

    demo = [(s, p) for s, p in rows if p.is_seed]
    real = [(s, p) for s, p in rows if not p.is_seed]

    tags: dict[str, int] = {}
    for s, _ in rows:
        for t in (s.tags or "").split(","):
            t = t.strip()
            if t:
                tags[t] = tags.get(t, 0) + 1

    facts = {
        "стратегий_опубликовано": len(rows),
        "из_них_демонстрационных": len(demo),
        "реальных": len(real),
        "enough_data": bool(real),
        "статистика_достоверна": (
            "да" if real else
            "НЕТ — все опубликованные стратегии демонстрационные, их показатели "
            "сгенерированы и не являются результатами торговли"),
        "теги": dict(sorted(tags.items(), key=lambda kv: -kv[1])[:10]),
        "подписки_платные_включены": False,
        "реальные_стратегии": [
            {"название": s.name, "тип_цены": s.price_type.value,
             "цена_в_месяц": s.price_monthly}
            for s, _ in real[:10]
        ],
    }

    if not real:
        fallback = (
            f"**Маркетплейс: {len(rows)} стратегий, все демонстрационные**\n\n"
            f"Показатели демо-стратегий сгенерированы для примера — это не "
            f"результаты торговли. Реальных стратегий от пользователей пока нет.\n\n"
            f"Платные подписки отключены до подтверждённой статистики доходности.")
    else:
        lines = [f"**Маркетплейс: {len(rows)} стратегий "
                 f"({len(real)} реальных, {len(demo)} демонстрационных)**", ""]
        for s, _ in real[:10]:
            price = ("бесплатно" if s.price_monthly == 0
                     else f"{s.price_monthly:g}/мес")
            lines.append(f"• {s.name} — {price}")
        fallback = "\n".join(lines)

    return await _insight(
        "Опиши содержимое маркетплейса: сколько стратегий реальных, сколько "
        "демонстрационных, какие темы преобладают. Прямо скажи, что показатели "
        "демо-стратегий сгенерированы. Не рекомендуй подписки.",
        facts, fallback)
