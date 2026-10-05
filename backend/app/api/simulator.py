"""Simulator API — a practice terminal, not an order router.

Every endpoint resolves the account through `simulator.get_account`, which scopes
by `user_id`. An account id belonging to another user, or to one of the platform's
own record-keeping accounts, resolves to None and returns 404 — so no request can
reach a row it does not own, and nothing here can touch the measured track record.

There is no counterpart that sends a real order. See `app/services/simulator.py`
for why that is a boundary rather than a gap.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.paper import PaperTrade
from app.models.user import User
from app.services import simulator

logger = logging.getLogger(__name__)
router = APIRouter()


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    starting_balance: float = Field(default=simulator.STARTING_BALANCE, gt=0)
    risk_per_trade_pct: float = Field(default=1.0, gt=0, le=10)
    currency: str = Field(default="RUB", pattern="^(RUB|USD|EUR)$")


class OpenRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    action: str = Field(pattern="^(buy|sell)$")
    units: float | None = Field(default=None, gt=0)
    take_profit: float | None = Field(default=None, gt=0)
    stop_loss: float | None = Field(default=None, gt=0)
    signal_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None


@router.get("/quote/{ticker}")
async def quote(ticker: str, user: User = Depends(get_current_user)):
    """Current price for the order form, with its source named.

    The source matters to the person placing the order: MOEX ISS is delayed
    ~15 minutes on the free feed, crypto is real-time.
    """
    from app.services.live_price import asset_class, get_live_price

    q = await get_live_price(ticker.upper())
    if not q or not q.get("price"):
        raise HTTPException(404, f"Нет цены по {ticker.upper()}")
    return {
        **q,
        "asset_class": asset_class(ticker.upper()),
        "commission_pct": round(simulator.commission_rate(ticker.upper()) * 100, 3),
        "delayed": q.get("source") == "MOEX ISS",
    }


@router.get("/candles/{ticker}")
async def candles(ticker: str, days: int = Query(120, ge=5, le=730),
                  user: User = Depends(get_current_user)):
    """Daily candles for the terminal chart, any asset class."""
    from datetime import date, timedelta

    from app.services.backtesting_real import detect_source, fetch_candles

    to = date.today()
    frm = to - timedelta(days=days)
    rows = await fetch_candles(ticker.upper(), frm.isoformat(), to.isoformat())
    if not rows:
        raise HTTPException(404, f"Нет свечей по {ticker.upper()}")
    return {
        "ticker": ticker.upper(),
        "source": detect_source(ticker.upper()),
        "candles": rows,
    }


@router.get("/accounts")
async def list_accounts(user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    """This user's simulator accounts. Creates the first one on demand."""
    await simulator.ensure_user_account(db, user)
    accounts = await simulator.user_accounts(db, user)
    return {
        "accounts": [
            {
                "id": str(a.id),
                "name": a.name,
                "currency": a.currency,
                "starting_balance": round(a.starting_balance, 2),
                "balance": round(a.balance, 2),
                "risk_per_trade_pct": round(a.risk_per_trade * 100, 2),
            }
            for a in accounts
        ],
        "max_accounts": simulator.MAX_ACCOUNTS_PER_USER,
        "disclosure_ru": simulator.SIM_DISCLOSURE["ru"],
    }


@router.post("/accounts", status_code=201)
async def create_account(body: AccountCreate,
                         user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)):
    """An extra account, so two sets of rules can be compared."""
    try:
        acc = await simulator.create_account(
            db, user, body.name, body.starting_balance,
            body.risk_per_trade_pct / 100, body.currency,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"id": str(acc.id), "name": acc.name,
            "balance": round(acc.balance, 2), "currency": acc.currency}


@router.get("/portfolio")
async def get_portfolio(account_id: uuid.UUID | None = None,
                        user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    """Open positions with live P&L, account equity, realised history."""
    acc = await simulator.get_account(db, user, account_id)
    if not acc:
        raise HTTPException(404, "Счёт не найден")
    return await simulator.portfolio(db, acc)


@router.post("/positions")
async def open_position(body: OpenRequest,
                        user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    """Open a virtual position at the current price."""
    acc = await simulator.get_account(db, user, body.account_id)
    if not acc:
        raise HTTPException(404, "Счёт не найден")
    try:
        return await simulator.open_position(
            db, acc, body.ticker, body.action, units=body.units,
            take_profit=body.take_profit, stop_loss=body.stop_loss,
            signal_id=body.signal_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/positions/{trade_id}/close")
async def close_position(trade_id: uuid.UUID,
                         user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)):
    """Close a position at the current price."""
    trade = (await db.execute(
        select(PaperTrade).where(PaperTrade.id == trade_id)
    )).scalar_one_or_none()
    if not trade:
        raise HTTPException(404, "Позиция не найдена")

    # Ownership is checked through the account, not the trade: this is what stops
    # a guessed id from closing a position on the platform's own account.
    acc = await simulator.get_account(db, user, trade.account_id)
    if not acc:
        raise HTTPException(404, "Позиция не найдена")

    try:
        return await simulator.close_position(db, acc, trade)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/history")
async def get_history(account_id: uuid.UUID | None = None,
                      limit: int = Query(50, ge=1, le=200),
                      user: User = Depends(get_current_user),
                      db: AsyncSession = Depends(get_db)):
    """Closed trades on this account, newest first."""
    acc = await simulator.get_account(db, user, account_id)
    if not acc:
        raise HTTPException(404, "Счёт не найден")
    return {"trades": await simulator.history(db, acc, limit)}


@router.post("/reset")
async def reset(account_id: uuid.UUID | None = None,
                user: User = Depends(get_current_user),
                db: AsyncSession = Depends(get_db)):
    """Delete this account's trades and restore the starting balance."""
    acc = await simulator.get_account(db, user, account_id)
    if not acc:
        raise HTTPException(404, "Счёт не найден")
    return await simulator.reset_account(db, acc)
