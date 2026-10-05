"""Win rate taken from measured outcomes, or nothing at all.

Expected value, Profit Factor and Kelly size are all functions of the win rate.
The formulas in expert_trading.py are correct; the input was not. It came from
constants:

    main.py:135          win_rate = 0.60
    signal_chart.py:228  0.65 / 0.55 / 0.45 by trend alignment

Neither was measured. The platform's actual record at the time this was written is
0 wins out of 11 closed trades — so every "EV +1.8% на сделку" published in a VIP
card was arithmetic on an assumption that the platform's own data contradicts.

A number derived from an assumption and displayed as a calculation is worse than no
number: the reader cannot tell which it is. So below the sample threshold this
returns None and the caller omits the whole block instead of substituting a guess.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Same floor as the public track record: a rate over fewer trades is noise.
MIN_SAMPLE = 30


async def measured_win_rate(db: AsyncSession, provider=None) -> dict:
    """Win rate over closed, non-seed trades. `rate` is None below MIN_SAMPLE.

    With a provider, measures that provider only — a platform-wide rate says
    nothing about one source. Without one, measures everything.
    """
    from app.models.signal import Signal, SignalStatus
    from app.services.signal_quality import is_seed_signal, not_excluded

    q = select(Signal).where(
        Signal.status.in_((SignalStatus.CLOSED_TP, SignalStatus.CLOSED_SL)),
        # Duplicated closed rows counted one outcome twice, which on a sample of
        # eleven moved the rate by nine points.
        not_excluded(),
    )
    if provider is not None:
        q = q.where(Signal.provider_id == provider.id)

    rows = [s for s in (await db.execute(q)).scalars().all() if not is_seed_signal(s)]

    relays = 0
    if provider is None:
        # Platform-wide, one market outcome must count once. Two channels relaying
        # the same trade (both BestStocks feeds published the same HBAN loss) are
        # two correct provider records but a single observation of what the market
        # did, and counting it twice overstates the sample the MIN_SAMPLE gate is
        # waiting for. Per-provider scope keeps every row: there the duplication
        # does not exist.
        seen, unique = set(), []
        for s in rows:
            key = (s.ticker, s.action, s.entry_price, s.take_profit,
                   s.stop_loss, s.status)
            if key in seen:
                relays += 1
                continue
            seen.add(key)
            unique.append(s)
        rows = unique

    wins = sum(1 for s in rows if s.status == SignalStatus.CLOSED_TP)
    n = len(rows)

    out = {
        "closed": n,
        "wins": wins,
        "min_sample": MIN_SAMPLE,
        "enough_data": n >= MIN_SAMPLE,
        "rate": None,
        "scope": "provider" if provider is not None else "platform",
        # How many rows were dropped as the same trade seen in another channel.
        "cross_channel_duplicates": relays,
    }
    if out["enough_data"]:
        out["rate"] = wins / n
    return out


async def expert_metrics(db: AsyncSession, signal, provider=None,
                         tp_pct: float | None = None,
                         sl_pct: float | None = None) -> dict:
    """EV / Profit Factor / Kelly — only when a measured win rate exists.

    Returns {"available": False, "reason": ...} otherwise, so the caller renders
    nothing rather than a plausible-looking figure.
    """
    wr = await measured_win_rate(db, provider)
    if not wr["enough_data"]:
        return {
            "available": False,
            "reason": (f"Мат. ожидание не рассчитано: измеренных сделок "
                       f"{wr['closed']}, нужно {wr['min_sample']}. "
                       f"Считать его от предполагаемого win rate значит выдавать "
                       f"допущение за расчёт."),
            **wr,
        }

    if tp_pct is None or sl_pct is None:
        entry = signal.entry_price or 0
        if not entry or not signal.take_profit or not signal.stop_loss:
            return {"available": False, "reason": "нет уровней для расчёта", **wr}
        tp_pct = abs(signal.take_profit - entry) / entry * 100
        sl_pct = abs(entry - signal.stop_loss) / entry * 100

    from app.services.expert_trading import expected_value, kelly_position_size

    ev = expected_value(wr["rate"], tp_pct, sl_pct)
    kelly = kelly_position_size(
        wr["rate"], tp_pct, sl_pct, 100_000,
        signal.entry_price, signal.stop_loss or signal.entry_price * 0.97,
    )
    return {
        "available": True,
        "ev_per_trade_pct": ev.get("expected_value_pct"),
        "profit_factor": ev.get("profit_factor"),
        "edge_pct": ev.get("edge_pct"),
        "kelly_half_pct": getattr(kelly, "half_kelly_pct", None),
        "win_rate_used": round(wr["rate"] * 100, 1),
        **wr,
    }
