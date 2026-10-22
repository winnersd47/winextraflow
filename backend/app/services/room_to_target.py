"""How much open space a signal's target has in front of it.

The idea comes from a trading channel analysed on 2026-10-16, which called it
"запас хода": before asking whether a target is attractive, ask whether price
has anywhere to go — or whether it must first break through levels it has
already failed at.

It is worth testing here because it addresses the platform's largest measured
failure directly. Replaying 80 stored signals against candles showed the band
with the most distant targets losing 7.04% per trade against 0.41% for the
nearest ones; `signal_geometry` explains part of that statistically (a target
four stops away is reached less often), but says nothing about WHY a particular
target is out of reach. A prior swing high sitting between entry and target is a
concrete reason.

Nothing here gates anything on its own. It produces a number; whether that
number separates winners from losers is a question for the eval set, and the
answer decides whether it earns a place in signal_quality. The project has been
burned once by a plausible-sounding factor that turned out to be anti-predictive.
"""

import logging

logger = logging.getLogger(__name__)

# A swing needs this many bars on each side to count as a level the market
# actually respected, rather than noise.
SWING_LOOKBACK = 3
# How far back to look for levels. Older than this and the market has usually
# forgotten them.
HISTORY_DAYS = 180


def swing_levels(candles: list[dict], lookback: int = SWING_LOOKBACK
                 ) -> tuple[list[float], list[float]]:
    """Swing highs and lows: a bar that is the extreme of its neighbourhood."""
    highs, lows = [], []
    n = len(candles)
    for i in range(lookback, n - lookback):
        window = candles[i - lookback:i + lookback + 1]
        try:
            h = float(candles[i].get("high") or 0)
            lo = float(candles[i].get("low") or 0)
            if h and h >= max(float(c.get("high") or 0) for c in window):
                highs.append(h)
            if lo and lo <= min(float(c.get("low") or 1e18) for c in window):
                lows.append(lo)
        except (TypeError, ValueError):
            continue
    return highs, lows


def room(entry: float, target: float, action: str,
         candles: list[dict]) -> dict:
    """Obstacles between entry and target, as a plain count and distance.

    `obstacles` is how many prior swing levels price must pass to reach the
    target. `first_obstacle_share` is how far along the path the nearest one
    sits, 0..1 — a value of 0.2 means the first barrier appears after a fifth of
    the journey, and four fifths of the move depends on breaking it.
    """
    out = {
        "available": False, "obstacles": None,
        "first_obstacle": None, "first_obstacle_share": None,
        "reason": "",
    }
    if not candles or len(candles) < SWING_LOOKBACK * 2 + 2:
        out["reason"] = "мало свечей для поиска уровней"
        return out
    if not entry or not target or entry <= 0:
        out["reason"] = "нет уровней"
        return out

    highs, lows = swing_levels(candles)
    is_buy = (action or "").lower() == "buy"
    # A buy climbs through prior highs; a sell falls through prior lows.
    levels = highs if is_buy else lows
    span = abs(target - entry)
    if span <= 0:
        out["reason"] = "цель совпадает со входом"
        return out

    if is_buy:
        between = [lv for lv in levels if entry < lv < target]
    else:
        between = [lv for lv in levels if target < lv < entry]

    out["available"] = True
    out["obstacles"] = len(between)
    if between:
        nearest = min(between, key=lambda lv: abs(lv - entry))
        out["first_obstacle"] = round(nearest, 6)
        out["first_obstacle_share"] = round(abs(nearest - entry) / span, 3)
        out["reason"] = (f"между входом и целью {len(between)} прежних "
                         f"экстремум{'ов' if len(between) != 1 else ''}")
    else:
        out["first_obstacle_share"] = 1.0
        out["reason"] = "до цели нет прежних экстремумов"
    return out


async def room_for_signal(ticker: str, entry: float, target: float,
                          action: str, as_of=None) -> dict:
    """`room` for one signal, fetching its own history.

    `as_of` restricts history to bars strictly before that date, so a replay of
    a past signal cannot see levels that only formed afterwards.
    """
    from datetime import date, timedelta

    from app.services.backtesting_real import fetch_candles

    end = as_of or date.today()
    start = end - timedelta(days=HISTORY_DAYS)
    try:
        candles = await fetch_candles(ticker, start.isoformat(), end.isoformat())
    except Exception as e:
        return {"available": False, "obstacles": None,
                "reason": f"нет истории: {type(e).__name__}"}

    if as_of:
        cutoff = as_of.isoformat()
        candles = [c for c in candles
                   if str(c.get("date") or c.get("begin") or "")[:10] < cutoff]
    return room(entry, target, action, candles)
