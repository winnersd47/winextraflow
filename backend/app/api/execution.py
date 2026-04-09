"""Execution API — manage exchange accounts and execute signals."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.exchange_account import ExchangeAccount
from app.models.order import Order
from app.models.signal import Signal
from app.models.user import User
from app.schemas.execution import (
    ExchangeAccountCreate,
    ExchangeAccountResponse,
    ExchangeAccountUpdate,
    ExecuteRequest,
    OrderList,
    OrderResponse,
)
from app.services.execution import encrypt_value, execution_service

router = APIRouter()


# ─── Exchange Accounts ─────────────────────────────────────

@router.post("/accounts", response_model=ExchangeAccountResponse, status_code=201)
async def create_account(
    data: ExchangeAccountCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Add a new exchange account with encrypted API keys."""
    account = ExchangeAccount(
        user_id=user.id,
        exchange=data.exchange,
        label=data.label,
        api_key_encrypted=encrypt_value(data.api_key),
        api_secret_encrypted=encrypt_value(data.api_secret),
        auto_execute=data.auto_execute,
        min_confidence=data.min_confidence,
        max_position_pct=data.max_position_pct,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.get("/accounts", response_model=list[ExchangeAccountResponse])
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ExchangeAccount)
        .where(ExchangeAccount.user_id == user.id)
        .order_by(ExchangeAccount.created_at.desc())
    )
    return result.scalars().all()


@router.patch("/accounts/{account_id}", response_model=ExchangeAccountResponse)
async def update_account(
    account_id: uuid.UUID,
    data: ExchangeAccountUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ExchangeAccount).where(
            ExchangeAccount.id == account_id,
            ExchangeAccount.user_id == user.id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(404, "Account not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    await db.commit()
    await db.refresh(account)
    return account


@router.delete("/accounts/{account_id}", status_code=204)
async def delete_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ExchangeAccount).where(
            ExchangeAccount.id == account_id,
            ExchangeAccount.user_id == user.id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(404, "Account not found")
    await db.delete(account)
    await db.commit()


# ─── Execute Signals ───────────────────────────────────────

@router.post("/execute/{signal_id}", response_model=OrderResponse)
async def execute_signal(
    signal_id: uuid.UUID,
    data: ExecuteRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Manually execute a signal on a specific exchange account."""
    signal = (await db.execute(
        select(Signal).where(Signal.id == signal_id)
    )).scalar_one_or_none()
    if not signal:
        raise HTTPException(404, "Signal not found")

    account = (await db.execute(
        select(ExchangeAccount).where(
            ExchangeAccount.id == data.exchange_account_id,
            ExchangeAccount.user_id == user.id,
            ExchangeAccount.is_active == True,
        )
    )).scalar_one_or_none()
    if not account:
        raise HTTPException(404, "Exchange account not found or inactive")

    order = await execution_service.execute_signal(
        db,
        signal=signal,
        account=account,
        user_id=user.id,
        order_type=data.order_type,
        quantity=data.quantity,
    )
    return order


# ─── Orders ───────────────────────────────────────────────

@router.get("/orders", response_model=OrderList)
async def list_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    total = (await db.execute(
        select(func.count()).select_from(Order).where(Order.user_id == user.id)
    )).scalar()
    result = await db.execute(
        select(Order)
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return OrderList(items=result.scalars().all(), total=total)
