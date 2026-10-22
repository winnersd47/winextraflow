"""Run published signals through virtual accounts.

Purpose: build a record that cannot be argued with. The platform currently has 7
measured closed trades, which is nothing, and it has no way to accumulate more
quickly because the analyst-derived signals used to carry annual targets. Every
published signal is now also opened here at the published levels and settled at
whichever level the market reaches — no discretion, no re-labelling.

Two invariants make the record trustworthy:

  * levels are frozen at open time. `PaperTrade` copies entry/TP/SL out of the
    signal, so later edits to the signal cannot change a recorded outcome.
  * one trade per (account, signal). Re-running the sync never double-counts.

`sync_open` opens what is missing, `settle` closes what the market resolved. Both
are idempotent, so they are safe on a cron.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import PaperAccount, PaperTrade, PaperTradeStatus
from app.models.signal import Signal, SignalAction, SignalStatus
from app.services.position_sizing import position_size

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Keeping the platform record separate from users' practice accounts.
#
# The web simulator lets a person open trades by hand on their own PaperAccount.
# Those trades share these tables, and if they ever leaked into the platform's
# numbers the measured record would become meaningless — someone practising with
# deliberately bad entries would move the published win rate.
#
# Every query that feeds a public number goes through these two helpers rather
# than filtering by hand at the call site.
# ---------------------------------------------------------------------------

def platform_accounts(q):
    """Restrict a PaperAccount query to the platform's own measured record.

    Two exclusions, not one. `user_id IS NULL` drops users' practice accounts.
    `scope == "platform"` drops the evaluation account, which also has a NULL
    user_id and would otherwise have walked straight into the published numbers
    carrying sources nobody has measured yet.
    """
    return q.where(PaperAccount.user_id.is_(None),
                   PaperAccount.scope == "platform")


def platform_trades(q):
    """Restrict a PaperTrade query to pipeline-opened trades on platform accounts.

    Both conditions, though either would do today: `opened_manually` guards
    against a user account being mistaken for a platform one, and the account
    filter guards against a manual trade written without the flag.
    """
    return q.where(
        PaperTrade.opened_manually.is_(False),
        PaperTrade.account_id.in_(
            select(PaperAccount.id).where(PaperAccount.user_id.is_(None),
                                          PaperAccount.scope == "platform")
        ),
    )

DEFAULT_ACCOUNTS = [
    # name, currency, balance, risk, min_wef, scope
    ("Основной 100k ₽", "RUB", 100_000.0, 0.01, 0, "platform"),
    ("Только сильные сигналы", "RUB", 100_000.0, 0.01, 65, "platform"),
    ("Агрессивный 2%", "RUB", 100_000.0, 0.02, 0, "platform"),
    # Sources on trial. They are measured here and nowhere else until they have
    # MIN_SAMPLE closed trades of their own — the forex scalping channels need
    # 67-87% of trades to win just to break even, and no one knows yet whether
    # they clear it. Mixing that into the platform's record would answer the
    # question with the one number the project cannot afford to get wrong.
    ("Оценка новых источников", "USD", 10_000.0, 0.01, 0, "evaluation"),
]


async def ensure_accounts(db: AsyncSession) -> list[PaperAccount]:
    """Create the default accounts once. Returns all accounts."""
    # Every account the platform owns, not just the ones in the published
    # record. `platform_accounts` narrows to scope="platform" so the evaluation
    # account stays out of the numbers — but using that same filter HERE meant
    # the evaluation account was never seen as existing, and a fresh copy was
    # created on every cron run. Eight duplicates accumulated in one morning.
    existing = (await db.execute(
        select(PaperAccount).where(PaperAccount.user_id.is_(None))
    )).scalars().all()
    have = {a.name for a in existing}
    created = []
    for name, cur, bal, risk, min_wef, scope in DEFAULT_ACCOUNTS:
        if name in have:
            continue
        acc = PaperAccount(name=name, currency=cur, starting_balance=bal, balance=bal,
                           risk_per_trade=risk, min_wef=min_wef, scope=scope)
        db.add(acc)
        created.append(acc)
    if created:
        await db.commit()
        logger.info(f"Paper accounts created: {[a.name for a in created]}")
    return existing + created


async def sync_open(db: AsyncSession, account: PaperAccount) -> int:
    """Open a virtual position for every eligible ACTIVE signal not yet traded."""
    traded = set((await db.execute(
        select(PaperTrade.signal_id).where(PaperTrade.account_id == account.id)
    )).scalars().all())

    # An account only trades the sources its scope covers. Without this the
    # platform's own record would quietly absorb every channel put on trial.
    from app.models.provider import Provider
    on_trial = set((await db.execute(
        select(Provider.id).where(Provider.paper_only.is_(True))
    )).scalars().all())
    scope = getattr(account, "scope", "platform") or "platform"

    signals = (await db.execute(
        select(Signal).where(
            Signal.status == SignalStatus.ACTIVE,
            Signal.take_profit.isnot(None),
            Signal.stop_loss.isnot(None),
        ).order_by(Signal.created_at.desc()).limit(500)
    )).scalars().all()

    from app.services.signal_quality import is_seed_signal
    opened = 0
    for s in signals:
        if s.id in traded or is_seed_signal(s):
            continue
        trial = s.provider_id in on_trial
        if (scope == "evaluation") != trial:
            continue
        wef = round((s.ai_confidence or 0) * 100)
        if wef < account.min_wef:
            continue
        size = position_size(account.balance, s.entry_price, s.stop_loss,
                             account.risk_per_trade)
        if not size or size["position"] <= 0:
            continue
        db.add(PaperTrade(
            account_id=account.id, signal_id=s.id, ticker=s.ticker,
            action=s.action.value, entry_price=s.entry_price,
            take_profit=s.take_profit, stop_loss=s.stop_loss, wef_at_open=wef,
            position_value=size["position"], units=size["units"],
            risk_money=size["risk_money"],
        ))
        opened += 1
    if opened:
        await db.commit()
    return opened


async def settle(db: AsyncSession, account: PaperAccount) -> dict:
    """Close virtual positions whose signal has resolved, and update the balance.

    The settling level comes from the trade's own frozen copy, so a trade closed
    here always reports the distance that was published — never a live price.
    """
    open_trades = (await db.execute(
        select(PaperTrade).where(
            PaperTrade.account_id == account.id,
            PaperTrade.status == PaperTradeStatus.OPEN,
        )
    )).scalars().all()
    if not open_trades:
        return {"closed": 0, "cancelled": 0}

    sig_by_id = {
        s.id: s for s in (await db.execute(
            select(Signal).where(Signal.id.in_([t.signal_id for t in open_trades]))
        )).scalars().all()
    }

    closed = cancelled = 0
    for t in open_trades:
        s = sig_by_id.get(t.signal_id)
        if not s:
            continue

        if s.status in (SignalStatus.CLOSED_TP, SignalStatus.CLOSED_SL):
            won = s.status == SignalStatus.CLOSED_TP
            level = t.take_profit if won else t.stop_loss
            if not level:
                continue
            pct = (level - t.entry_price) / t.entry_price * 100
            if t.action == SignalAction.SELL.value:
                pct = -pct
            money = t.position_value * pct / 100

            t.status = PaperTradeStatus.CLOSED_TP if won else PaperTradeStatus.CLOSED_SL
            t.close_price = level
            t.result_pct = pct
            t.result_money = money
            t.closed_at = datetime.now(timezone.utc)
            account.balance += money
            closed += 1

        elif s.status == SignalStatus.EXPIRED:
            # Never reached either level. Recorded as cancelled, not as a loss:
            # counting it as a loss would understate the strategy, counting it as a
            # win would overstate it. It simply was not a trade.
            t.status = PaperTradeStatus.CANCELLED
            t.closed_at = datetime.now(timezone.utc)
            cancelled += 1

    await db.commit()
    return {"closed": closed, "cancelled": cancelled}


async def account_stats(db: AsyncSession, account: PaperAccount) -> dict:
    """Performance of one account. Percentages only once the sample supports them."""
    from app.api.track_record import MIN_SAMPLE

    q = select(PaperTrade).where(PaperTrade.account_id == account.id)
    # A platform account reports only pipeline trades. A user's simulator account
    # reports its own, so no flag filter there.
    if account.user_id is None:
        q = q.where(PaperTrade.opened_manually.is_(False))
    trades = (await db.execute(q)).scalars().all()
    done = [t for t in trades if t.status in (PaperTradeStatus.CLOSED_TP,
                                              PaperTradeStatus.CLOSED_SL)]
    wins = [t for t in done if t.status == PaperTradeStatus.CLOSED_TP]
    gross_win = sum(t.result_money or 0 for t in wins)
    gross_loss = -sum(t.result_money or 0 for t in done if (t.result_money or 0) < 0)

    out = {
        "account": account.name,
        "currency": account.currency,
        "risk_per_trade_pct": round(account.risk_per_trade * 100, 2),
        "min_wef": account.min_wef,
        "starting_balance": round(account.starting_balance, 2),
        "balance": round(account.balance, 2),
        "open_trades": sum(1 for t in trades if t.status == PaperTradeStatus.OPEN),
        "closed_trades": len(done),
        "cancelled_trades": sum(1 for t in trades if t.status == PaperTradeStatus.CANCELLED),
        "min_sample": MIN_SAMPLE,
        "enough_data": len(done) >= MIN_SAMPLE,
    }
    # Absolute equity is a fact regardless of sample size; ratios are not.
    out["pnl_money"] = round(account.balance - account.starting_balance, 2)
    out["pnl_pct_of_start"] = round(
        (account.balance - account.starting_balance) / account.starting_balance * 100, 2
    ) if account.starting_balance else None

    if out["enough_data"]:
        out["win_rate_pct"] = round(len(wins) / len(done) * 100, 1)
        out["avg_result_pct"] = round(sum(t.result_pct or 0 for t in done) / len(done), 2)
        out["profit_factor"] = round(gross_win / gross_loss, 2) if gross_loss else None
    else:
        out["win_rate_pct"] = out["avg_result_pct"] = out["profit_factor"] = None
        out["notice_ru"] = (
            f"Закрытых сделок: {len(done)}. Win rate и profit factor показываем "
            f"после {MIN_SAMPLE} сделок — на меньшей выборке это шум."
        )
    return out


async def run_all(db: AsyncSession) -> list[dict]:
    """One full cycle over every account: open what is new, settle what resolved."""
    accounts = await ensure_accounts(db)
    report = []
    for acc in accounts:
        opened = await sync_open(db, acc)
        settled = await settle(db, acc)
        stats = await account_stats(db, acc)
        stats["opened_now"] = opened
        stats["closed_now"] = settled["closed"]
        stats["cancelled_now"] = settled["cancelled"]
        report.append(stats)
    return report
