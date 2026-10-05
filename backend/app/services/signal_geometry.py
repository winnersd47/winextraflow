"""Per-signal historical check: was this target reachable before this stop?

A single signal cannot be backtested — one trade is not a strategy, there is nothing
to test. What *can* be tested is the geometry the signal embodies: given this
instrument's own volatility, how often did price travel `tp_mult × ATR` in the
signal's direction before it travelled `sl_mult × ATR` against it?

That question is answerable from candles alone, with no entry rule and no forecast:
walk every historical bar, pretend to enter at its close, and see which level the
following bars reached first.

## What this measures — and what it does not

It measures whether the **target is achievable** at this instrument's volatility.
It says nothing about whether the signal is right about direction: the walk enters
on every bar, not on the signal's condition.

So "цель достигалась раньше стопа в 68 случаях из 100" is true and useful.
"Вероятность успеха сигнала 68%" would be a lie — and it is exactly the kind of lie
this project has been removing. The two differ by the entry rule, which is not
tested here.

Guards, for the same reason as everywhere else in the codebase:

  * no ratio below MIN_OCCURRENCES — a rate over eight samples is noise
  * the walk never looks at bars before the simulated entry
  * the final bars are excluded: a setup opened near the end of the window has not
    had time to resolve, and counting it as "unresolved" would bias the rate down
"""

import logging

logger = logging.getLogger(__name__)

# Below this the hit rate is not reported at all.
MIN_OCCURRENCES = 30
# How many bars a setup gets to resolve before it is called undecided.
MAX_BARS_TO_RESOLVE = 30
LOOKBACK_DAYS = 730


# The answer changes only when a new daily bar closes, and the walk costs a
# candle fetch plus a few hundred iterations. Cached per (ticker, action, day) so a
# burst of signals on one instrument does not refetch two years of history each time.
_CACHE: dict[tuple, dict] = {}


async def geometry_hit_rate_cached(ticker: str, action: str,
                                   tp_mult: float = 4.0, sl_mult: float = 2.0) -> dict:
    """geometry_hit_rate with a per-day cache. Use this from the pipeline."""
    from datetime import date
    key = (ticker.upper(), action.lower(), tp_mult, sl_mult, date.today().isoformat())
    if key not in _CACHE:
        _CACHE[key] = await geometry_hit_rate(ticker, action, tp_mult, sl_mult)
        # Bound the cache: one entry per instrument per day is plenty, and this runs
        # in a long-lived process.
        if len(_CACHE) > 400:
            for k in list(_CACHE)[:200]:
                _CACHE.pop(k, None)
    return _CACHE[key]


async def geometry_hit_rate(ticker: str, action: str,
                            tp_mult: float = 4.0, sl_mult: float = 2.0,
                            lookback_days: int = LOOKBACK_DAYS) -> dict:
    """How often `tp_mult x ATR` was reached before `sl_mult x ATR` against.

    Returns a dict that always carries `enough_data`; when it is False the rate
    fields are None rather than a small-sample number.
    """
    from datetime import datetime, timedelta, timezone

    from app.services.backtesting_real import fetch_candles

    out = {
        "ticker": ticker, "action": action.lower(),
        "tp_mult": tp_mult, "sl_mult": sl_mult,
        "lookback_days": lookback_days,
        "occurrences": 0, "reached_target": 0, "hit_stop": 0, "undecided": 0,
        "hit_rate_pct": None, "enough_data": False,
        "min_occurrences": MIN_OCCURRENCES,
        "note": None,
    }

    date_from = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    date_to = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        candles = await fetch_candles(ticker, date_from, date_to)
    except Exception as e:
        logger.debug(f"geometry: candles failed for {ticker}: {e}")
        out["note"] = "нет исторических данных по инструменту"
        return out

    bars = [c for c in (candles or [])
            if c.get("close") and c.get("high") and c.get("low")]
    if len(bars) < MIN_OCCURRENCES + MAX_BARS_TO_RESOLVE:
        out["note"] = (f"истории мало: {len(bars)} свечей, нужно минимум "
                       f"{MIN_OCCURRENCES + MAX_BARS_TO_RESOLVE}")
        return out

    is_buy = action.lower() == "buy"
    # One ATR per entry bar, computed only from bars at or before it — using a
    # single ATR for the whole window would leak later volatility into earlier
    # entries.
    atr_window = 14
    reached = stopped = undecided = 0

    # Stop before the tail so every counted setup had room to resolve.
    last_entry = len(bars) - MAX_BARS_TO_RESOLVE
    for i in range(atr_window, last_entry):
        trs = []
        prev_close = bars[i - atr_window].get("close")
        for c in bars[i - atr_window + 1:i + 1]:
            h, l, cl = c["high"], c["low"], c["close"]
            trs.append(h - l if prev_close is None
                       else max(h - l, abs(h - prev_close), abs(l - prev_close)))
            prev_close = cl
        atr = sum(trs) / len(trs) if trs else 0
        entry = bars[i]["close"]
        if atr <= 0 or entry <= 0:
            continue

        tp = entry + atr * tp_mult if is_buy else entry - atr * tp_mult
        sl = entry - atr * sl_mult if is_buy else entry + atr * sl_mult

        verdict = None
        for c in bars[i + 1:i + 1 + MAX_BARS_TO_RESOLVE]:
            hi, lo = c["high"], c["low"]
            tp_hit = hi >= tp if is_buy else lo <= tp
            sl_hit = lo <= sl if is_buy else hi >= sl
            # Both in one bar: count the stop. Intraday order is unknown, and
            # assuming the favourable one would flatter every result.
            if sl_hit:
                verdict = "stop"
                break
            if tp_hit:
                verdict = "target"
                break
        if verdict == "target":
            reached += 1
        elif verdict == "stop":
            stopped += 1
        else:
            undecided += 1

    total = reached + stopped
    out.update(occurrences=total, reached_target=reached, hit_stop=stopped,
               undecided=undecided)
    if total >= MIN_OCCURRENCES:
        out["hit_rate_pct"] = round(reached / total * 100, 1)
        out["enough_data"] = True
        out["note"] = (f"на {ticker} за {lookback_days // 365} г.: цель "
                       f"{tp_mult:g}×ATR достигалась раньше стопа {sl_mult:g}×ATR "
                       f"в {reached} из {total} случаев")
    else:
        out["note"] = (f"разрешившихся сетапов {total}, для доли нужно "
                       f"{MIN_OCCURRENCES}")
    return out


def breakeven_hit_rate(tp_mult: float, sl_mult: float) -> float:
    """Hit rate at which this geometry stops losing money, ignoring costs.

    The number a historical rate has to be compared against: a 4:2 setup needs only
    a third of trades to work, which is the whole reason win rate alone says nothing
    (see the lesson «Миф: профессионал закрывает в плюс почти все сделки»).
    """
    if tp_mult <= 0:
        return 100.0
    return round(sl_mult / (tp_mult + sl_mult) * 100, 1)
