"""The seven advisors, as pure functions over a candle window.

These mirror the MQL5 experts in mt5/ (WEF_S1…WEF_S7) so the same rules can be
measured here, on real candles, without a terminal and without money. The
constants are the EAs' own `input` defaults — when one is changed there, change
it here, or the two stop describing the same strategy:

    S1  WEF_S1_TrendFollowing.mq5   FastEMA 12, SlowEMA 26, SlopeBars 5
    S2  WEF_S2_MeanReversion.mq5    RSI 14 at 30/70, BB(20, 2), flat ≤ 0.5 ATR
    S3  WEF_S3_RangeFlat.mq5        channel 30 bars ≤ 6 ATR, edge 15%
    S4  WEF_S4_Breakout.mq5         squeeze 20 bars ≤ 4 ATR, volume ≥ 1.5×
    S5  WEF_S5_MultiIndicator.mq5   EMA + MACD + RSI, 3 votes of 3
    S6  WEF_S6_StatArb.mq5          z-score 50 bars, entry at ±2σ
    S7  WEF_S7_AI.mq5               asks the bridge — needs a key, see below

Every function takes the candles UP TO AND INCLUDING the bar being decided and
returns "buy", "sell" or None. Nothing reads past the end of the window: a
replay that can see the next bar measures nothing but its own cheating.

Levels come from WEF_Common.mqh — stop at 2 ATR, target at 4 ATR. That is R:R
2.0, a breakeven share of 33%, comfortably inside the gate's 70% ceiling.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# ── WEF_Common.mqh ──────────────────────────────────────────────────────────
STOP_ATR_MULT = 2.0
TARGET_ATR_MULT = 4.0
ATR_PERIOD = 14

# ── per-advisor inputs, named as in the .mq5 files ──────────────────────────
S1_FAST_EMA, S1_SLOW_EMA, S1_SLOPE_BARS = 12, 26, 5
S2_RSI_PERIOD, S2_OVERSOLD, S2_OVERBOUGHT = 14, 30.0, 70.0
S2_BAND_PERIOD, S2_BAND_DEV, S2_FLAT_EMA, S2_FLAT_SLOPE_ATR = 20, 2.0, 50, 0.5
S3_CHANNEL_BARS, S3_MAX_RANGE_ATR, S3_EDGE_TOLERANCE = 30, 6.0, 0.15
S4_SQUEEZE_BARS, S4_MAX_SQUEEZE_ATR, S4_VOLUME_MULT = 20, 4.0, 1.5
S5_MIN_VOTES = 3
S6_Z_PERIOD, S6_Z_ENTRY = 50, 2.0

MIN_CANDLES = 60   # the longest lookback any advisor needs, plus headroom


# ═══ indicators ═══════════════════════════════════════════════════════════

def _closes(c): return [float(x["close"]) for x in c]


def ema(values: list[float], period: int) -> list[float]:
    """Full EMA series. The EAs read a slope across bars, not one value."""
    if not values:
        return []
    k = 2.0 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(k * v + (1 - k) * out[-1])
    return out


def atr(candles: list[dict], period: int = ATR_PERIOD) -> float:
    """Wilder true range, averaged over `period` — 0.0 when undefined.

    A zero ATR means no volatility measure, and every caller must refuse to
    trade on it rather than divide by it: the EAs all open with `if(atr <= 0)
    return`.
    """
    if len(candles) < period + 1:
        return 0.0
    trs = []
    for i in range(len(candles) - period, len(candles)):
        prev_close = float(candles[i - 1]["close"])
        h, l = float(candles[i]["high"]), float(candles[i]["low"])
        trs.append(max(h - l, abs(h - prev_close), abs(l - prev_close)))
    return sum(trs) / len(trs) if trs else 0.0


def rsi(values: list[float], period: int = 14) -> float:
    if len(values) < period + 1:
        return 50.0
    gains = losses = 0.0
    for i in range(len(values) - period, len(values)):
        d = values[i] - values[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    if losses == 0:
        return 100.0
    rs = (gains / period) / (losses / period)
    return 100.0 - 100.0 / (1.0 + rs)


def bollinger(values: list[float], period: int, dev: float) -> tuple[float, float]:
    """(upper, lower). Equal bounds when there is no deviation to speak of."""
    window = values[-period:]
    mean = sum(window) / len(window)
    var = sum((v - mean) ** 2 for v in window) / len(window)
    sd = math.sqrt(var)
    return mean + dev * sd, mean - dev * sd


def macd(values: list[float]) -> tuple[float, float]:
    """(macd, signal) — 12/26/9, the EA's defaults."""
    line = [f - s for f, s in zip(ema(values, 12), ema(values, 26))]
    return line[-1], ema(line, 9)[-1]


# ═══ the seven ════════════════════════════════════════════════════════════

def s1_trend_following(c: list[dict]) -> str | None:
    """Fast EMA above slow, price above fast, slow EMA sloping the same way."""
    px = _closes(c)
    if len(px) < S1_SLOW_EMA + S1_SLOPE_BARS + 1:
        return None
    fast, slow = ema(px, S1_FAST_EMA), ema(px, S1_SLOW_EMA)
    slope = slow[-1] - slow[-1 - S1_SLOPE_BARS]
    price = px[-1]
    if fast[-1] > slow[-1] and price > fast[-1] and slope > 0:
        return "buy"
    if fast[-1] < slow[-1] and price < fast[-1] and slope < 0:
        return "sell"
    return None


def s2_mean_reversion(c: list[dict]) -> str | None:
    """Oversold at the lower band — but only while the market is going nowhere.

    The flat filter is the whole point: mean reversion into a trend is just
    catching a falling knife, so the EA refuses unless the 50-EMA has moved
    less than half an ATR over ten bars.
    """
    px = _closes(c)
    if len(px) < max(S2_FLAT_EMA, S2_BAND_PERIOD) + 11:
        return None
    a = atr(c)
    if a <= 0:
        return None
    flat = ema(px, S2_FLAT_EMA)
    if abs(flat[-1] - flat[-11]) > S2_FLAT_SLOPE_ATR * a:
        return None
    upper, lower = bollinger(px, S2_BAND_PERIOD, S2_BAND_DEV)
    r, price = rsi(px, S2_RSI_PERIOD), px[-1]
    if r <= S2_OVERSOLD and price <= lower:
        return "buy"
    if r >= S2_OVERBOUGHT and price >= upper:
        return "sell"
    return None


def s3_range_flat(c: list[dict]) -> str | None:
    """Buy the floor of a channel, sell the ceiling — if it is really a channel."""
    if len(c) < S3_CHANNEL_BARS + ATR_PERIOD + 1:
        return None
    a = atr(c)
    if a <= 0:
        return None
    window = c[-S3_CHANNEL_BARS:]
    top = max(float(x["high"]) for x in window)
    bot = min(float(x["low"]) for x in window)
    height = top - bot
    if height <= 0 or height > S3_MAX_RANGE_ATR * a:
        return None
    band = height * S3_EDGE_TOLERANCE
    price = float(c[-1]["close"])
    if price <= bot + band:
        return "buy"
    if price >= top - band:
        return "sell"
    return None


def s4_breakout(c: list[dict]) -> str | None:
    """Leave a squeeze on volume. Without the volume test it is just noise."""
    if len(c) < S4_SQUEEZE_BARS + ATR_PERIOD + 2:
        return None
    a = atr(c)
    if a <= 0:
        return None
    # The squeeze is the bars BEFORE the breaking one; including it would
    # measure the range the breakout already widened.
    window = c[-S4_SQUEEZE_BARS - 1:-1]
    top = max(float(x["high"]) for x in window)
    bot = min(float(x["low"]) for x in window)
    height = top - bot
    if height <= 0 or height > S4_MAX_SQUEEZE_ATR * a:
        return None
    vols = [float(x.get("volume") or 0) for x in window]
    avg = sum(vols) / len(vols) if vols else 0.0
    last_vol = float(c[-1].get("volume") or 0)
    if avg <= 0 or last_vol < S4_VOLUME_MULT * avg:
        return None
    close = float(c[-1]["close"])
    if close > top:
        return "buy"
    if close < bot:
        return "sell"
    return None


def s5_multi_indicator(c: list[dict]) -> str | None:
    """Three independent votes, all three required by default."""
    px = _closes(c)
    if len(px) < 40:
        return None
    fast, slow = ema(px, 12), ema(px, 26)
    m, sig = macd(px)
    r = rsi(px, 14)

    bull = sum([fast[-1] > slow[-1], m > sig, r > 50])
    bear = sum([fast[-1] < slow[-1], m < sig, r < 50])
    if bull >= S5_MIN_VOTES:
        return "buy"
    if bear >= S5_MIN_VOTES:
        return "sell"
    return None


def s6_stat_arb(c: list[dict]) -> str | None:
    """Single-symbol z-score: fade a move two deviations from its own mean."""
    px = _closes(c)
    if len(px) < S6_Z_PERIOD:
        return None
    window = px[-S6_Z_PERIOD:]
    mean = sum(window) / len(window)
    sd = math.sqrt(sum((v - mean) ** 2 for v in window) / len(window))
    if sd <= 0:
        return None
    z = (px[-1] - mean) / sd
    if z <= -S6_Z_ENTRY:
        return "buy"
    if z >= S6_Z_ENTRY:
        return "sell"
    return None


def s7_ai(c: list[dict]) -> str | None:
    """The LLM advisor. Not replayable offline, and not faked.

    WEF_S7_AI.mq5 sends sixty candles to the bridge and trades the answer. A
    replay would need one model call per bar — thousands of calls and a bill —
    and substituting a rule here would report a number under the name of a
    strategy that never produced it. Reported as "not measured" instead.
    """
    return None


@dataclass(frozen=True)
class Advisor:
    id: str
    name: str
    signal: callable
    replayable: bool = True


ADVISORS: tuple[Advisor, ...] = (
    Advisor("S1", "Trend Following", s1_trend_following),
    Advisor("S2", "Mean Reversion", s2_mean_reversion),
    Advisor("S3", "Range / Flat", s3_range_flat),
    Advisor("S4", "Breakout", s4_breakout),
    Advisor("S5", "Multi-Indicator", s5_multi_indicator),
    Advisor("S6", "Stat Arb (z-score)", s6_stat_arb),
    Advisor("S7", "AI", s7_ai, replayable=False),
)


def levels(action: str, price: float, a: float) -> tuple[float, float]:
    """(take_profit, stop_loss) at the EAs' 4 ATR / 2 ATR."""
    if action == "buy":
        return price + TARGET_ATR_MULT * a, price - STOP_ATR_MULT * a
    return price - TARGET_ATR_MULT * a, price + STOP_ATR_MULT * a
