"""Hand-driven trading simulator on the platform's own price feed.

Distinct from `paper_trading.py`, which opens positions automatically from
published signals to build the platform's measured record. This module is the
opposite: a person decides what to open, and the result belongs to them alone.
Trades written here carry `opened_manually=True` on an account with `user_id`
set, and every query behind a public number filters both out.

Nothing here can reach a broker. There are no API keys, no exchange adapters and
no order routing — a position is a row in `paper_trades`, and closing one moves a
number in `paper_accounts.balance`. That is a deliberate limit, not a stage on the
way to real execution: routing client orders is licensed activity, and this
platform is registered as an information service.

What a simulator cannot reproduce
---------------------------------
Fills come from `get_live_price`, the same feed the signal monitor uses, and they
are honest about being approximations:

  * no spread. A real buy fills at the ask, above the last price, and a sell at
    the bid. On liquid instruments this is small; on a wide-spread one it is not.
  * no slippage or liquidity limit. The simulator will happily "buy" a position
    larger than the whole visible book at an unchanged price.
  * MOEX quotes are delayed ~15 minutes on the free ISS feed, so a fill can be a
    quarter-hour stale. Crypto is real-time.
  * no funding, no overnight carry, no margin call.

Commission IS modelled, because leaving it out is the difference between a
strategy that looks marginally profitable and one that is not — it is the most
common reason a plan that works on paper loses money in an account.

`SIM_DISCLOSURE` travels with every portfolio response so the interface cannot
present these results as if they were achievable unchanged.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import PaperAccount, PaperTrade, PaperTradeStatus
from app.services.live_price import asset_class, get_live_price
from app.services.position_sizing import position_size

logger = logging.getLogger(__name__)

STARTING_BALANCE = 100_000.0
DEFAULT_RISK = 0.01

# Bounds, so one account cannot fill the table or a runaway client cannot open
# thousands of rows.
MAX_ACCOUNTS_PER_USER = 3
MAX_OPEN_POSITIONS = 20
MAX_POSITION_SHARE = 0.25          # of equity, matching position_sizing

# Round-turn commission per side, as a fraction of position value. Deliberately
# at the pessimistic end of what a retail account actually pays, so the simulator
# never flatters a strategy.
COMMISSION = {
    "crypto": 0.0010,              # Bybit/Binance spot taker ~0.10%
    "moex": 0.0005,                # RU broker ~0.05% per side
    "forex": 0.0002,
    "us_stock": 0.0005,
    "other": 0.0005,
}

SIM_DISCLOSURE = {
    "ru": "Симулятор. Исполнение по последней цене без спреда, проскальзывания и "
          "лимита ликвидности — в реальном счёте вход был бы хуже. Котировки MOEX "
          "запаздывают ~15 минут, крипта в реальном времени. Комиссия учитывается. "
          "Финансирование, перенос через ночь и маржин-колл не моделируются. "
          "Реальные заявки не отправляются: платформа информационная.",
    "commission_note_ru": "Комиссия: крипта 0.10%, MOEX 0.05%, FX 0.02% с каждой стороны.",
}


def commission_rate(ticker: str) -> float:
    """Commission per side for this instrument's class."""
    return COMMISSION.get(asset_class(ticker), COMMISSION["other"])


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

async def user_accounts(db: AsyncSession, user) -> list[PaperAccount]:
    """This user's simulator accounts, oldest first."""
    return list((await db.execute(
        select(PaperAccount)
        .where(PaperAccount.user_id == user.id)
        .order_by(PaperAccount.created_at)
    )).scalars().all())


async def ensure_user_account(db: AsyncSession, user) -> PaperAccount:
    """Return the user's account, creating a first one on demand."""
    existing = await user_accounts(db, user)
    if existing:
        return existing[0]

    acc = PaperAccount(
        user_id=user.id,
        name="Симулятор",
        currency="RUB",
        starting_balance=STARTING_BALANCE,
        balance=STARTING_BALANCE,
        risk_per_trade=DEFAULT_RISK,
        notes="Тренировочный счёт. Реальные заявки не отправляются.",
    )
    db.add(acc)
    await db.commit()
    await db.refresh(acc)
    logger.info(f"Simulator account created for user {user.id}")
    return acc


async def get_account(db: AsyncSession, user, account_id: uuid.UUID | None = None
                      ) -> PaperAccount | None:
    """One account belonging to this user, or their default.

    Always scoped by `user_id`, so an id belonging to someone else — or to a
    platform account — resolves to None rather than to the row.
    """
    if account_id is None:
        return await ensure_user_account(db, user)
    return (await db.execute(
        select(PaperAccount).where(
            PaperAccount.id == account_id,
            PaperAccount.user_id == user.id,
        )
    )).scalar_one_or_none()


async def create_account(db: AsyncSession, user, name: str, balance: float,
                         risk_per_trade: float, currency: str = "RUB") -> PaperAccount:
    """An additional account, so different rules can be compared side by side."""
    if len(await user_accounts(db, user)) >= MAX_ACCOUNTS_PER_USER:
        raise ValueError(f"Максимум счетов: {MAX_ACCOUNTS_PER_USER}")
    if balance <= 0:
        raise ValueError("Стартовый баланс должен быть больше нуля")
    if not 0 < risk_per_trade <= 0.1:
        raise ValueError("Риск на сделку — от 0 до 10%")

    acc = PaperAccount(
        user_id=user.id, name=name[:60], currency=currency,
        starting_balance=balance, balance=balance,
        risk_per_trade=risk_per_trade,
        notes="Тренировочный счёт. Реальные заявки не отправляются.",
    )
    db.add(acc)
    await db.commit()
    await db.refresh(acc)
    return acc


async def reset_account(db: AsyncSession, account: PaperAccount) -> dict:
    """Wipe the account's history and restore the starting balance.

    Deletes rows rather than marking them, because a practice account's purpose
    is starting over. Nothing here feeds the platform record, so there is no
    measured history to protect.
    """
    n = (await db.execute(
        select(func.count()).select_from(PaperTrade)
        .where(PaperTrade.account_id == account.id)
    )).scalar() or 0

    for t in (await db.execute(
        select(PaperTrade).where(PaperTrade.account_id == account.id)
    )).scalars().all():
        await db.delete(t)

    account.balance = account.starting_balance
    await db.commit()
    return {"deleted_trades": n, "balance": account.balance}


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------

async def open_position(db: AsyncSession, account: PaperAccount, ticker: str,
                        action: str, units: float | None = None,
                        take_profit: float | None = None,
                        stop_loss: float | None = None,
                        signal_id: uuid.UUID | None = None) -> dict:
    """Open a virtual position at the current price.

    Size comes either from `units` given explicitly, or from fixed-fractional
    sizing off the stop — the same `position_size` the signal cards use, so what
    the platform teaches and what the simulator does are one rule.
    """
    ticker = ticker.upper().strip()
    action = action.lower().strip()
    if action not in ("buy", "sell"):
        raise ValueError("action: buy или sell")

    open_now = (await db.execute(
        select(func.count()).select_from(PaperTrade).where(
            PaperTrade.account_id == account.id,
            PaperTrade.status == PaperTradeStatus.OPEN,
        )
    )).scalar() or 0
    if open_now >= MAX_OPEN_POSITIONS:
        raise ValueError(f"Максимум открытых позиций: {MAX_OPEN_POSITIONS}")

    quote = await get_live_price(ticker)
    if not quote or not quote.get("price"):
        raise ValueError(f"Нет цены по {ticker}. Проверьте тикер.")
    price = float(quote["price"])
    if price <= 0:
        raise ValueError(f"Источник вернул нулевую цену по {ticker}")

    # Levels must sit on the correct side of entry, or the position is
    # unresolvable — a long with its target below entry closes instantly.
    if take_profit is not None:
        if action == "buy" and take_profit <= price:
            raise ValueError("Для покупки тейк-профит должен быть выше цены входа")
        if action == "sell" and take_profit >= price:
            raise ValueError("Для продажи тейк-профит должен быть ниже цены входа")
    if stop_loss is not None:
        if action == "buy" and stop_loss >= price:
            raise ValueError("Для покупки стоп-лосс должен быть ниже цены входа")
        if action == "sell" and stop_loss <= price:
            raise ValueError("Для продажи стоп-лосс должен быть выше цены входа")

    equity = account.balance
    if units is not None:
        if units <= 0:
            raise ValueError("Количество должно быть больше нуля")
        position_value = units * price
        risk_money = abs(price - stop_loss) * units if stop_loss else 0.0
    elif stop_loss is not None:
        size = position_size(equity, price, stop_loss, account.risk_per_trade)
        if not size or size.get("position", 0) <= 0:
            raise ValueError("Не удалось рассчитать размер позиции")
        position_value = size["position"]
        units = size["units"]
        risk_money = size["risk_money"]
    else:
        raise ValueError("Укажите количество или стоп-лосс для расчёта размера")

    cap = equity * MAX_POSITION_SHARE
    if position_value > cap:
        raise ValueError(
            f"Позиция {position_value:,.0f} превышает лимит "
            f"{MAX_POSITION_SHARE:.0%} от счёта ({cap:,.0f}). "
            f"Это ограничение симулятора: одна сделка не должна решать судьбу счёта."
            .replace(",", " ")
        )

    fee = position_value * commission_rate(ticker)
    if fee >= equity:
        raise ValueError("Недостаточно средств даже на комиссию")

    # Commission is taken at open, as a broker does. The rest of the position
    # value is not deducted: this models a single-position P&L account rather
    # than cash settlement, which keeps `balance` readable as equity-at-rest.
    account.balance = equity - fee

    trade = PaperTrade(
        account_id=account.id,
        signal_id=signal_id,
        opened_manually=True,
        ticker=ticker,
        action=action,
        entry_price=price,
        take_profit=take_profit,
        stop_loss=stop_loss,
        position_value=position_value,
        units=units,
        risk_money=risk_money,
        status=PaperTradeStatus.OPEN,
    )
    db.add(trade)
    await db.commit()
    await db.refresh(trade)

    return {
        "trade": _trade_dict(trade),
        "fill_price": price,
        "price_source": quote.get("source"),
        "commission": round(fee, 2),
        "balance": round(account.balance, 2),
        "disclosure_ru": SIM_DISCLOSURE["ru"],
    }


async def close_position(db: AsyncSession, account: PaperAccount,
                         trade: PaperTrade) -> dict:
    """Close a position at the current price and settle it into the balance."""
    if trade.status != PaperTradeStatus.OPEN:
        raise ValueError("Позиция уже закрыта")

    quote = await get_live_price(trade.ticker)
    if not quote or not quote.get("price"):
        raise ValueError(f"Нет цены по {trade.ticker} — позицию нельзя оценить")
    price = float(quote["price"])

    gross = _pnl_money(trade, price)
    fee = trade.position_value * commission_rate(trade.ticker)   # exit side
    net = gross - fee

    trade.close_price = price
    trade.result_money = round(net, 2)
    trade.result_pct = round(net / trade.position_value * 100, 2) if trade.position_value else 0.0
    # A hand-closed position is neither a target nor a stop. It is recorded by
    # which side of break-even it landed on, after costs.
    trade.status = (PaperTradeStatus.CLOSED_TP if net >= 0
                    else PaperTradeStatus.CLOSED_SL)
    trade.closed_at = datetime.now(timezone.utc)
    account.balance = account.balance + net

    await db.commit()
    await db.refresh(trade)
    return {
        "trade": _trade_dict(trade),
        "close_price": price,
        "price_source": quote.get("source"),
        "gross_pnl": round(gross, 2),
        "commission": round(fee, 2),
        "net_pnl": round(net, 2),
        "balance": round(account.balance, 2),
    }


async def settle_levels(db: AsyncSession, account: PaperAccount) -> dict:
    """Close any open position whose target or stop the market has reached.

    Called when the portfolio is read, so levels take effect without a cron. A
    position is checked against the last price only — the simulator does not see
    intrabar highs and lows, so a level touched and left inside the polling gap
    is missed. It errs toward not closing, which is the harmless direction.
    """
    rows = (await db.execute(
        select(PaperTrade).where(
            PaperTrade.account_id == account.id,
            PaperTrade.status == PaperTradeStatus.OPEN,
        )
    )).scalars().all()

    closed = []
    for t in rows:
        if t.take_profit is None and t.stop_loss is None:
            continue
        quote = await get_live_price(t.ticker)
        if not quote or not quote.get("price"):
            continue
        price = float(quote["price"])

        hit_tp = hit_sl = False
        if t.action == "buy":
            hit_tp = t.take_profit is not None and price >= t.take_profit
            hit_sl = t.stop_loss is not None and price <= t.stop_loss
        else:
            hit_tp = t.take_profit is not None and price <= t.take_profit
            hit_sl = t.stop_loss is not None and price >= t.stop_loss

        if not (hit_tp or hit_sl):
            continue
        # Both at once means the gap jumped past both levels; the stop is the
        # conservative reading and the one a real account would more likely get.
        level = t.stop_loss if hit_sl else t.take_profit

        gross = _pnl_money(t, level)
        fee = t.position_value * commission_rate(t.ticker)
        net = gross - fee
        t.close_price = level
        t.result_money = round(net, 2)
        t.result_pct = round(net / t.position_value * 100, 2) if t.position_value else 0.0
        t.status = PaperTradeStatus.CLOSED_SL if hit_sl else PaperTradeStatus.CLOSED_TP
        t.closed_at = datetime.now(timezone.utc)
        account.balance = account.balance + net
        closed.append({"ticker": t.ticker, "level": level,
                       "kind": "stop" if hit_sl else "target",
                       "net_pnl": round(net, 2)})

    if closed:
        await db.commit()
    return {"closed": closed}


async def portfolio(db: AsyncSession, account: PaperAccount) -> dict:
    """Open positions with live unrealised P&L, plus realised history summary."""
    await settle_levels(db, account)

    rows = (await db.execute(
        select(PaperTrade).where(PaperTrade.account_id == account.id)
        .order_by(PaperTrade.opened_at.desc())
    )).scalars().all()

    open_rows = [t for t in rows if t.status == PaperTradeStatus.OPEN]
    done = [t for t in rows if t.status in (PaperTradeStatus.CLOSED_TP,
                                            PaperTradeStatus.CLOSED_SL)]

    positions, unrealised = [], 0.0
    for t in open_rows:
        quote = await get_live_price(t.ticker)
        price = float(quote["price"]) if quote and quote.get("price") else None
        pnl = _pnl_money(t, price) if price else None
        if pnl is not None:
            unrealised += pnl
        d = _trade_dict(t)
        d.update({
            "current_price": price,
            "unrealised_pnl": round(pnl, 2) if pnl is not None else None,
            "unrealised_pct": (round(pnl / t.position_value * 100, 2)
                               if pnl is not None and t.position_value else None),
            "price_source": quote.get("source") if quote else None,
            "price_unavailable": price is None,
        })
        positions.append(d)

    realised = sum(t.result_money or 0 for t in done)
    wins = sum(1 for t in done if (t.result_money or 0) > 0)

    out = {
        "account": {
            "id": str(account.id),
            "name": account.name,
            "currency": account.currency,
            "starting_balance": round(account.starting_balance, 2),
            "balance": round(account.balance, 2),
            "equity": round(account.balance + unrealised, 2),
            "risk_per_trade_pct": round(account.risk_per_trade * 100, 2),
        },
        "positions": positions,
        "open_count": len(open_rows),
        "max_open": MAX_OPEN_POSITIONS,
        "unrealised_pnl": round(unrealised, 2),
        "realised_pnl": round(realised, 2),
        "closed_count": len(done),
        "wins": wins,
        "disclosure_ru": SIM_DISCLOSURE["ru"],
        "commission_note_ru": SIM_DISCLOSURE["commission_note_ru"],
    }

    # The same sample floor the platform applies to itself. A win rate over four
    # practice trades tells the user nothing, and showing it would teach exactly
    # the habit the lessons argue against.
    from app.services.measured_stats import MIN_SAMPLE
    out["min_sample"] = MIN_SAMPLE
    out["enough_data"] = len(done) >= MIN_SAMPLE
    if out["enough_data"]:
        out["win_rate_pct"] = round(wins / len(done) * 100, 1)
    else:
        out["win_rate_pct"] = None
        out["notice_ru"] = (f"Win rate не показываем: закрытых сделок {len(done)}, "
                            f"нужно {MIN_SAMPLE}. На меньшей выборке это шум, "
                            f"а не результат.")
    return out


async def history(db: AsyncSession, account: PaperAccount, limit: int = 50) -> list[dict]:
    """Closed trades, newest first."""
    rows = (await db.execute(
        select(PaperTrade).where(
            PaperTrade.account_id == account.id,
            PaperTrade.status.in_((PaperTradeStatus.CLOSED_TP,
                                   PaperTradeStatus.CLOSED_SL)),
        ).order_by(PaperTrade.closed_at.desc()).limit(limit)
    )).scalars().all()
    return [_trade_dict(t) for t in rows]


# ---------------------------------------------------------------------------

def _pnl_money(trade: PaperTrade, price: float) -> float:
    """Gross P&L of a position at `price`, before commission."""
    delta = price - trade.entry_price
    if trade.action == "sell":
        delta = -delta
    return delta * trade.units


def _trade_dict(t: PaperTrade) -> dict:
    return {
        "id": str(t.id),
        "ticker": t.ticker,
        "action": t.action,
        "entry_price": t.entry_price,
        "take_profit": t.take_profit,
        "stop_loss": t.stop_loss,
        "units": round(t.units, 8),
        "position_value": round(t.position_value, 2),
        "risk_money": round(t.risk_money, 2) if t.risk_money else 0.0,
        "status": t.status.value,
        "close_price": t.close_price,
        "result_pct": t.result_pct,
        "result_money": t.result_money,
        "signal_id": str(t.signal_id) if t.signal_id else None,
        "opened_at": t.opened_at.isoformat() if t.opened_at else None,
        "closed_at": t.closed_at.isoformat() if t.closed_at else None,
    }
