"""Turn analyst recommendations into tradable levels.

Analyst-recommendation channels (beststocks and similar) publish a direction and a
target price — nothing else. The parser used to fill the gaps by arithmetic:

    entry = target / (1 + forecast_pct)      # a price nobody can trade at
    stop  = entry * 0.90                     # a stop the analyst never set

Both numbers then went out to paying subscribers as "вход" and "стоп", and the
resulting R:R was arithmetic on invented inputs. Ten of the eighteen closed real
trades carry that fabricated -10% stop, so their recorded loss measures the default
rather than the source.

What the source actually knows is the direction and the target. So:
  * entry comes from the live market — the price a reader can actually get
  * the stop comes from realized volatility (ATR), so it sits outside noise
  * the target stays as published, and the quality gate judges the R:R that results

A stop tighter than one ATR is noise-bait: four crypto signals with 0.8-1.4% stops
all closed at a loss within hours. MIN_STOP_ATR keeps stops outside that band.
"""

import logging

logger = logging.getLogger(__name__)

STOP_ATR_MULT = 2.0        # stop distance = 2 x ATR
TP_ATR_MULT = 4.0          # first target = 4 x ATR  ->  R:R 1:2 by construction
MIN_STOP_ATR = 1.0         # reject/widen anything tighter than 1 ATR
MIN_STOP_PCT = 0.010       # floor: never a stop tighter than 1%
MAX_STOP_PCT = 0.12        # cap: beyond this the position is not risk-controlled
ATR_DAYS = 30


async def atr_pct(ticker: str, days: int = ATR_DAYS) -> float | None:
    """Average True Range over `days`, as a fraction of the last close."""
    from datetime import datetime, timedelta, timezone
    from app.services.backtesting_real import fetch_candles

    date_from = (datetime.now(timezone.utc) - timedelta(days=days * 2)).strftime("%Y-%m-%d")
    date_to = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        candles = await fetch_candles(ticker, date_from, date_to)
    except Exception as e:
        logger.debug(f"ATR fetch failed for {ticker}: {e}")
        return None
    if not candles or len(candles) < 5:
        return None

    trs, prev_close = [], None
    for c in candles[-days:]:
        h, l, cl = c.get("high"), c.get("low"), c.get("close")
        if h is None or l is None or cl is None:
            continue
        tr = h - l if prev_close is None else max(h - l, abs(h - prev_close), abs(l - prev_close))
        trs.append(tr)
        prev_close = cl
    if not trs or not prev_close:
        return None
    return (sum(trs) / len(trs)) / prev_close


async def resolve_levels(ticker: str, action: str, entry: float,
                         take_profit: float | None, stop_loss: float | None,
                         derived: bool = False,
                         atr_override: float | None = None) -> dict:
    """Return market-anchored levels for a signal.

    `derived=True` means the parser invented the entry and stop (analyst format).
    `atr_override` is a caller-supplied ATR as a fraction of price — the MT5 bridge
    already computes it from the terminal's own candles, so passing it avoids a
    second fetch from a different price source, which would size the stop off data
    the trade will not be executed against.

    Returns {entry, take_profit, stop_loss, long_target, notes, usable}.
    Never raises — on any data failure it hands back the input unchanged so the
    normal quality gate still gets to judge it.
    """
    out = {"entry": entry, "take_profit": take_profit, "stop_loss": stop_loss,
           "long_target": None, "notes": [], "usable": True}
    is_buy = (action or "").lower() == "buy"

    # 1. Anchor the entry to the live market when the parser guessed it.
    if derived:
        try:
            from app.services.live_price import get_live_price
            live = (await get_live_price(ticker) or {}).get("price") or 0
            if live > 0:
                if entry and abs(entry - live) / live > 0.005:
                    out["notes"].append(
                        f"вход по рынку {live:g} вместо расчётного {entry:g}")
                out["entry"] = live
            else:
                out["notes"].append("живая цена недоступна — вход расчётный")
        except Exception as e:
            logger.debug(f"live entry failed for {ticker}: {e}")

    entry = out["entry"]
    if not entry or entry <= 0:
        out["usable"] = False
        return out

    # 2. Stop from realized volatility, not a flat percentage.
    atr = atr_override if atr_override else await atr_pct(ticker)
    if atr:
        want = min(max(atr * STOP_ATR_MULT, MIN_STOP_PCT), MAX_STOP_PCT)
        cur_pct = abs(entry - stop_loss) / entry if stop_loss else None
        floor = max(atr * MIN_STOP_ATR, MIN_STOP_PCT)
        if stop_loss is None or derived:
            out["stop_loss"] = round(entry * (1 - want) if is_buy else entry * (1 + want), 6)
            out["notes"].append(f"стоп по волатильности: {want:.1%} (ATR {atr:.1%})")
        elif cur_pct is not None and cur_pct < floor:
            # Source's own stop, but inside the noise band — widen it and say so.
            out["stop_loss"] = round(entry * (1 - want) if is_buy else entry * (1 + want), 6)
            out["notes"].append(
                f"стоп источника {cur_pct:.1%} внутри шума (ATR {atr:.1%}) → расширен до {want:.1%}")
    elif derived:
        out["notes"].append("ATR недоступен — стоп остался расчётным")

    # 3. A tradable first target.
    #
    # Analyst targets are annual price forecasts: +21% (NTRA), +25% (BANE), +49%
    # (ONTO). Paired with a ~5% volatility stop, such a signal resolves at the stop
    # long before the target, so in practice it can only produce losses — and it
    # produces no results at all for months, which is why the channel showed none.
    #
    # So the first target sits at a horizon comparable to the stop, and the analyst
    # number is carried separately as the long-horizon reference. Only ever moved
    # closer: we never invent a target more ambitious than the source's.
    if atr and out["take_profit"] and entry:
        near = entry * (1 + atr * TP_ATR_MULT) if is_buy else entry * (1 - atr * TP_ATR_MULT)
        far = out["take_profit"]
        far_pct = abs(far - entry) / entry
        if (is_buy and near < far) or (not is_buy and near > far):
            out["long_target"] = far
            out["take_profit"] = round(near, 6)
            out["notes"].append(
                f"цель {far_pct:.0%} — прогноз на год; ближняя цель "
                f"{abs(near - entry) / entry:.1%} ({TP_ATR_MULT:g}×ATR), "
                f"годовой ориентир сохранён отдельно")

    return out
