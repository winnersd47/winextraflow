"""Paper (demo) account API — public, read-only.

Public on purpose: the point of these accounts is that anyone can check them. They
are the platform's own record, kept under rules fixed in advance — position sized
by risk, levels frozen at open, ratios withheld until the sample supports them.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.paper import PaperAccount, PaperTrade, PaperTradeStatus
from app.services.paper_trading import account_stats, platform_accounts, platform_trades

router = APIRouter()

CLOSED = (PaperTradeStatus.CLOSED_TP, PaperTradeStatus.CLOSED_SL)


@router.get("/accounts")
async def list_accounts(db: AsyncSession = Depends(get_db)):
    """Every demo account with its current state."""
    accounts = (await db.execute(
        platform_accounts(select(PaperAccount)).order_by(PaperAccount.name)
    )).scalars().all()
    return {"accounts": [await account_stats(db, a) for a in accounts]}


@router.get("/trades")
async def list_trades(
    account: str | None = Query(None, description="Account name; all accounts if omitted"),
    status: str | None = Query(None, pattern="^(open|closed|cancelled)$"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Individual virtual trades, newest first."""
    # Public endpoint: platform trades only. A user's simulator history is served
    # by /api/v1/simulator/trades, which requires their own token.
    q = platform_trades(select(PaperTrade))
    if account:
        acc = (await db.execute(
            platform_accounts(select(PaperAccount)).where(PaperAccount.name == account)
        )).scalar_one_or_none()
        if not acc:
            raise HTTPException(404, "Account not found")
        q = q.where(PaperTrade.account_id == acc.id)
    if status == "open":
        q = q.where(PaperTrade.status == PaperTradeStatus.OPEN)
    elif status == "closed":
        q = q.where(PaperTrade.status.in_(CLOSED))
    elif status == "cancelled":
        q = q.where(PaperTrade.status == PaperTradeStatus.CANCELLED)

    rows = (await db.execute(
        q.order_by(PaperTrade.opened_at.desc()).limit(limit)
    )).scalars().all()

    return {
        "trades": [
            {
                "ticker": t.ticker,
                "action": t.action,
                "entry_price": t.entry_price,
                "take_profit": t.take_profit,
                "stop_loss": t.stop_loss,
                "wef_at_open": t.wef_at_open,
                "position_value": round(t.position_value, 2),
                "risk_money": round(t.risk_money, 2),
                "status": t.status.value,
                "close_price": t.close_price,
                "result_pct": round(t.result_pct, 2) if t.result_pct is not None else None,
                "result_money": round(t.result_money, 2) if t.result_money is not None else None,
                "opened_at": t.opened_at,
                "closed_at": t.closed_at,
            }
            for t in rows
        ],
        "count": len(rows),
    }


@router.get("/methodology")
async def methodology():
    """The rules these accounts run under, stated so results can be checked."""
    from app.api.track_record import MIN_SAMPLE
    from app.services.paper_trading import DEFAULT_ACCOUNTS
    from app.services.position_sizing import MAX_POSITION_SHARE
    from app.services.signal_levels import MIN_STOP_ATR, STOP_ATR_MULT, TP_ATR_MULT

    return {
        "ru": {
            "что_это": "Виртуальные счёты, торгующие каждый опубликованный сигнал по "
                       "тем уровням, которые были опубликованы. Не реальные деньги.",
            "правила": [
                f"Размер позиции — от риска: фиксированный % депозита делится на "
                f"расстояние до стопа. Не более {MAX_POSITION_SHARE:.0%} депозита в одну позицию.",
                "Уровни фиксируются в момент открытия и потом не меняются — "
                "поздняя правка сигнала не может изменить записанный результат.",
                "Одна сделка на сигнал: повторный запуск синхронизации не удваивает статистику.",
                f"Стоп по волатильности: {STOP_ATR_MULT:g}×ATR, не ближе {MIN_STOP_ATR:g}×ATR.",
                f"Ближняя цель: {TP_ATR_MULT:g}×ATR. Годовой прогноз аналитика хранится "
                f"отдельно и целью не считается.",
                "Сигнал, истёкший без достижения уровней, помечается «отменён», а не "
                "убытком: это не была сделка.",
                f"Win rate и profit factor не публикуются до {MIN_SAMPLE} закрытых сделок.",
            ],
            "счета": [
                {"название": n, "депозит": b, "валюта": c,
                 "риск_на_сделку": f"{r:.0%}",
                 "фильтр": f"WEF >= {w}%" if w else "без фильтра"}
                for n, c, b, r, w in DEFAULT_ACCOUNTS
            ],
        },
        "disclaimer_ru": "Результаты демо-счетов не являются обещанием доходности и не "
                         "являются инвестиционной рекомендацией.",
    }
