"""Track Record API — auditable public log of closed signals.

Credible signal services publish a full, row-by-row auditable record; the ones
that only advertise a win rate are the ones to distrust. This exposes every
closed signal with its outcome, plus aggregate stats that are WITHHELD until the
sample is large enough to mean anything.

  GET /track-record/summary   — aggregate stats (or "not enough data" notice)
  GET /track-record/signals   — paginated log of closed signals
  GET /track-record/by-market — breakdown per market
"""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.signal import Signal, SignalAction, SignalStatus
from app.models.provider import Provider

logger = logging.getLogger(__name__)
router = APIRouter()

# Below this many closed trades, aggregate percentages are noise — do not publish
# them as performance. Industry guidance is far higher (500+ for a real audit).
MIN_SAMPLE = 30

CLOSED = (SignalStatus.CLOSED_TP, SignalStatus.CLOSED_SL)

# Demo/seed rows must never enter a published track record — counting them would
# be inventing a performance history. seed_data marks them in raw_message.
SEED_MARKERS = ("auto-generated", "demo signal", "test signal")


def _is_seed(s: Signal) -> bool:
    raw = (s.raw_message or "").lower()
    return any(raw.startswith(m) or m in raw[:40] for m in SEED_MARKERS)


async def _closed_real(db: AsyncSession) -> list[Signal]:
    """Closed signals from real sources only (seed/demo excluded)."""
    rows = (await db.execute(select(Signal).where(Signal.status.in_(CLOSED)))).scalars().all()
    return [s for s in rows if not _is_seed(s)]


def _realized_pct(s: Signal) -> float | None:
    """P&L at the level that closed the trade — never the current market price."""
    if not s.entry_price:
        return None
    if s.status == SignalStatus.CLOSED_TP and s.take_profit:
        raw = (s.take_profit - s.entry_price) / s.entry_price * 100
    elif s.status == SignalStatus.CLOSED_SL and s.stop_loss:
        raw = (s.stop_loss - s.entry_price) / s.entry_price * 100
    else:
        return None
    return -raw if s.action == SignalAction.SELL else raw


def _market(ticker: str) -> str:
    from app.services.backtesting_real import detect_source
    from app.services.signal_chart import is_moex_futures
    t = (ticker or "").upper()
    if is_moex_futures(t):
        return "futures"
    return detect_source(t)


@router.get("/summary")
async def summary(db: AsyncSession = Depends(get_db)):
    """Aggregate performance. Stats stay hidden until MIN_SAMPLE closed trades."""
    rows = await _closed_real(db)
    trades = [(s, _realized_pct(s)) for s in rows]
    trades = [(s, p) for s, p in trades if p is not None]

    total = len(trades)
    if total < MIN_SAMPLE:
        return {
            "enough_data": False,
            "closed_trades": total,
            "min_sample": MIN_SAMPLE,
            "notice_ru": (
                f"Закрытых сделок: {total}. Публичную статистику доходности показываем "
                f"только после {MIN_SAMPLE} закрытых сделок — на меньшей выборке "
                f"проценты не значат ничего."
            ),
            "notice_en": (
                f"{total} closed trades so far. Aggregate performance is published only "
                f"after {MIN_SAMPLE} closed trades — smaller samples are noise."
            ),
        }

    wins = [p for _, p in trades if p > 0]
    losses = [p for _, p in trades if p <= 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    avg_win = gross_win / len(wins) if wins else 0.0
    avg_loss = gross_loss / len(losses) if losses else 0.0
    win_rate = len(wins) / total

    return {
        "enough_data": True,
        "closed_trades": total,
        "win_rate_pct": round(win_rate * 100, 1),
        "wins": len(wins),
        "losses": len(losses),
        "avg_win_pct": round(avg_win, 2),
        "avg_loss_pct": round(avg_loss, 2),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else None,
        "expectancy_pct": round(win_rate * avg_win - (1 - win_rate) * avg_loss, 3),
        "best_pct": round(max(p for _, p in trades), 2),
        "worst_pct": round(min(p for _, p in trades), 2),
        "disclaimer_ru": (
            "Результаты рассчитаны по уровню закрытия (TP/SL) без учёта комиссий и "
            "проскальзывания. Прошлые результаты не гарантируют будущих. "
            "Не является инвестиционной рекомендацией."
        ),
    }


@router.get("/signals")
async def signals(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    market: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Row-by-row log of closed signals — the part anyone can audit."""
    rows = sorted(await _closed_real(db),
                  key=lambda x: x.updated_at or x.created_at, reverse=True)[:500]

    items = []
    for s in rows:
        pct = _realized_pct(s)
        if pct is None:
            continue
        m = _market(s.ticker)
        if market and m != market:
            continue
        items.append({
            "id": str(s.id),
            "ticker": s.ticker,
            "market": m,
            "action": s.action.value,
            "entry": s.entry_price,
            "take_profit": s.take_profit,
            "stop_loss": s.stop_loss,
            "outcome": "tp" if s.status == SignalStatus.CLOSED_TP else "sl",
            "result_pct": round(pct, 2),
            "wef_score": round(s.ai_confidence * 100) if s.ai_confidence else None,
            "opened_at": s.created_at.isoformat() if s.created_at else None,
            "closed_at": s.updated_at.isoformat() if s.updated_at else None,
        })

    return {"total": len(items), "items": items[offset:offset + limit]}


@router.get("/by-market")
async def by_market(db: AsyncSession = Depends(get_db)):
    """Per-market breakdown. Each market carries its own sample-size caveat."""
    rows = await _closed_real(db)
    buckets: dict[str, list[float]] = {}
    for s in rows:
        pct = _realized_pct(s)
        if pct is None:
            continue
        buckets.setdefault(_market(s.ticker), []).append(pct)

    out = []
    for m, pcts in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        wins = [p for p in pcts if p > 0]
        out.append({
            "market": m,
            "closed_trades": len(pcts),
            "enough_data": len(pcts) >= MIN_SAMPLE,
            "win_rate_pct": round(len(wins) / len(pcts) * 100, 1) if len(pcts) >= MIN_SAMPLE else None,
            "avg_result_pct": round(sum(pcts) / len(pcts), 2) if len(pcts) >= MIN_SAMPLE else None,
        })
    return {"markets": out, "min_sample": MIN_SAMPLE}
