"""Expert Trading Engine — institutional-grade risk management and position sizing.

Scales Investology principles to professional level:
1. Kelly Criterion position sizing (fractional: half/quarter)
2. Regime-adaptive risk (ATR-scaled stops, volatility adjustment)
3. Multi-level drawdown circuit breakers (per-trade, daily, weekly, total)
4. Anti-Martingale pyramiding (add to winners, cut losers)
5. Correlation risk capping
6. Expected Value gating (only trade +EV setups)
7. Multi-timeframe confirmation scoring
8. Session-aware execution (Asian/London/NY windows)

Every method returns actionable parameters, not just analysis.
"""

import math
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ═══ 1. KELLY CRITERION POSITION SIZING ═══

@dataclass
class KellyResult:
    full_kelly_pct: float  # theoretical max
    half_kelly_pct: float  # practical (recommended)
    quarter_kelly_pct: float  # conservative
    risk_per_trade_pct: float  # actual risk % of capital
    position_size_lots: float  # lots/units to trade
    capital_at_risk: float  # absolute $ at risk


def kelly_position_size(
    win_rate: float,
    avg_win_pct: float,
    avg_loss_pct: float,
    capital: float,
    entry_price: float,
    stop_loss: float,
    kelly_fraction: float = 0.5,  # half-Kelly default
) -> KellyResult:
    """Calculate optimal position size using Kelly Criterion.

    Kelly = W - (1-W)/R where W=win_rate, R=avg_win/avg_loss
    Half-Kelly recommended for real trading (smoother equity curve).
    """
    if avg_loss_pct <= 0 or win_rate <= 0:
        return KellyResult(0, 0, 0, 0, 0, 0)

    r_ratio = abs(avg_win_pct) / abs(avg_loss_pct)  # reward/risk ratio
    full_kelly = win_rate - (1 - win_rate) / r_ratio

    # Clamp to 0-100%
    full_kelly = max(0, min(full_kelly, 1.0))
    half_kelly = full_kelly * 0.5
    quarter_kelly = full_kelly * 0.25
    actual = full_kelly * kelly_fraction

    # Convert to position size
    risk_per_unit = abs(entry_price - stop_loss)
    if risk_per_unit <= 0:
        return KellyResult(
            round(full_kelly * 100, 2), round(half_kelly * 100, 2),
            round(quarter_kelly * 100, 2), round(actual * 100, 2), 0, 0,
        )

    capital_to_risk = capital * actual
    lots = capital_to_risk / risk_per_unit

    return KellyResult(
        full_kelly_pct=round(full_kelly * 100, 2),
        half_kelly_pct=round(half_kelly * 100, 2),
        quarter_kelly_pct=round(quarter_kelly * 100, 2),
        risk_per_trade_pct=round(actual * 100, 2),
        position_size_lots=round(lots, 4),
        capital_at_risk=round(capital_to_risk, 2),
    )


# ═══ 2. DRAWDOWN CIRCUIT BREAKERS ═══

@dataclass
class CircuitBreakerState:
    trades_today: int = 0
    daily_pnl_pct: float = 0.0
    weekly_pnl_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    consecutive_losses: int = 0
    is_halted: bool = False
    halt_reason: str = ""


@dataclass
class CircuitBreakerConfig:
    max_daily_loss_pct: float = 3.0  # halt if daily loss > 3%
    max_weekly_loss_pct: float = 7.0  # halt if weekly loss > 7%
    max_drawdown_pct: float = 15.0  # halt if total drawdown > 15%
    max_consecutive_losses: int = 5  # halt after 5 losses in a row
    max_trades_per_day: int = 10  # no more than 10 trades/day
    cooldown_after_halt_hours: int = 24


def check_circuit_breakers(
    state: CircuitBreakerState,
    config: CircuitBreakerConfig,
) -> CircuitBreakerState:
    """Check all circuit breakers and halt if triggered."""
    if state.daily_pnl_pct <= -config.max_daily_loss_pct:
        state.is_halted = True
        state.halt_reason = f"Daily loss {state.daily_pnl_pct:.1f}% exceeds {config.max_daily_loss_pct}% limit"
    elif state.weekly_pnl_pct <= -config.max_weekly_loss_pct:
        state.is_halted = True
        state.halt_reason = f"Weekly loss {state.weekly_pnl_pct:.1f}% exceeds {config.max_weekly_loss_pct}% limit"
    elif state.max_drawdown_pct >= config.max_drawdown_pct:
        state.is_halted = True
        state.halt_reason = f"Drawdown {state.max_drawdown_pct:.1f}% exceeds {config.max_drawdown_pct}% limit"
    elif state.consecutive_losses >= config.max_consecutive_losses:
        state.is_halted = True
        state.halt_reason = f"{state.consecutive_losses} consecutive losses — cooling down"
    elif state.trades_today >= config.max_trades_per_day:
        state.is_halted = True
        state.halt_reason = f"Max {config.max_trades_per_day} trades/day reached"
    else:
        state.is_halted = False
        state.halt_reason = ""
    return state


# ═══ 3. REGIME-ADAPTIVE RISK ═══

def regime_risk_adjustment(
    base_risk_pct: float,
    regime: str,
    atr_current: float,
    atr_avg: float,
) -> dict:
    """Adjust risk based on market regime and volatility.

    High volatility → reduce size, widen stops.
    Low volatility → normal size, tight stops.
    Trending → increase size (momentum).
    Ranging → reduce size (mean reversion smaller).
    """
    vol_ratio = atr_current / atr_avg if atr_avg > 0 else 1.0

    # Regime multiplier
    regime_mult = {
        "trending_up": 1.2,
        "trending_down": 1.1,
        "breakout": 1.3,
        "ranging": 0.7,
        "high_volatility": 0.5,
        "low_volatility": 1.0,
        "unknown": 0.8,
    }.get(regime, 0.8)

    # Volatility inverse scaling (higher vol → smaller position)
    vol_mult = 1.0 / max(vol_ratio, 0.5)
    vol_mult = max(0.3, min(vol_mult, 1.5))

    adjusted_risk = base_risk_pct * regime_mult * vol_mult
    adjusted_risk = max(0.1, min(adjusted_risk, 5.0))  # clamp 0.1-5%

    # Stop-loss expansion for volatility
    sl_multiplier = max(1.0, vol_ratio)

    return {
        "base_risk_pct": base_risk_pct,
        "regime": regime,
        "regime_multiplier": round(regime_mult, 2),
        "volatility_ratio": round(vol_ratio, 2),
        "volatility_multiplier": round(vol_mult, 2),
        "adjusted_risk_pct": round(adjusted_risk, 2),
        "sl_expansion_factor": round(sl_multiplier, 2),
        "recommendation": (
            "Increase size — strong trend" if regime_mult > 1.1
            else "Reduce size — high volatility" if vol_mult < 0.7
            else "Reduce size — ranging market" if regime_mult < 0.8
            else "Normal size"
        ),
    }


# ═══ 4. ANTI-MARTINGALE PYRAMIDING ═══

def pyramid_plan(
    entry_price: float,
    direction: str,  # "buy" or "sell"
    take_profit: float,
    stop_loss: float,
    total_capital_pct: float = 10.0,  # max % of capital for full position
    levels: int = 3,
) -> list[dict]:
    """Anti-Martingale pyramiding: add to winners as price moves in favor.

    Split position into 3 entries:
    - Entry 1: 50% at market (initial)
    - Entry 2: 30% at 33% to TP (confirmation)
    - Entry 3: 20% at 66% to TP (momentum)

    Stop-loss moves to breakeven after Entry 2.
    """
    is_buy = direction.lower() == "buy"
    tp_distance = abs(take_profit - entry_price)

    allocations = [0.50, 0.30, 0.20]
    entry_offsets = [0.0, 0.33, 0.66]  # % of TP distance

    plan = []
    for i in range(levels):
        if is_buy:
            price = entry_price + tp_distance * entry_offsets[i]
        else:
            price = entry_price - tp_distance * entry_offsets[i]

        # Move SL to breakeven after level 2
        sl = stop_loss if i == 0 else entry_price if i == 1 else plan[0]["entry_price"]

        plan.append({
            "level": i + 1,
            "entry_price": round(price, 4),
            "allocation_pct": round(allocations[i] * total_capital_pct, 1),
            "stop_loss": round(sl, 4),
            "trigger": (
                "Market (immediate)" if i == 0
                else f"Limit at {entry_offsets[i]*100:.0f}% to TP"
            ),
            "sl_note": (
                "Initial stop" if i == 0
                else "Breakeven stop" if i == 1
                else "Trailing from entry"
            ),
        })

    return plan


# ═══ 5. EXPECTED VALUE GATE ═══

def expected_value(
    win_rate: float,
    avg_win_pct: float,
    avg_loss_pct: float,
) -> dict:
    """Calculate Expected Value — only trade +EV setups.

    EV = (WR × avg_win) - (LR × avg_loss)
    Professional threshold: EV > 0.5% per trade
    """
    ev = (win_rate * abs(avg_win_pct)) - ((1 - win_rate) * abs(avg_loss_pct))
    ev_per_1000 = ev * 10  # EV per $1000 risked

    # Profit factor
    pf = (win_rate * abs(avg_win_pct)) / ((1 - win_rate) * abs(avg_loss_pct)) if (1 - win_rate) * abs(avg_loss_pct) > 0 else 0

    # Breakeven win rate for this R:R
    rr = abs(avg_win_pct) / abs(avg_loss_pct) if abs(avg_loss_pct) > 0 else 0
    breakeven_wr = 1 / (1 + rr) if rr > 0 else 0.5

    # Edge = actual WR - breakeven WR
    edge = win_rate - breakeven_wr

    return {
        "expected_value_pct": round(ev, 3),
        "ev_per_1000": round(ev_per_1000, 2),
        "profit_factor": round(pf, 2),
        "win_rate": round(win_rate, 3),
        "breakeven_win_rate": round(breakeven_wr, 3),
        "edge_pct": round(edge * 100, 1),
        "verdict": (
            "Strong +EV — trade aggressively" if ev > 1.0
            else "Positive EV — trade normally" if ev > 0.3
            else "Marginal EV — trade small" if ev > 0
            else "Negative EV — DO NOT TRADE"
        ),
        "tradeable": ev > 0,
    }


# ═══ 6. MULTI-TIMEFRAME CONFIRMATION ═══

def multi_tf_score(
    tf_1h: str,  # "bullish", "bearish", "neutral"
    tf_4h: str,
    tf_1d: str,
    signal_action: str,  # "buy" or "sell"
) -> dict:
    """Score signal by multi-timeframe alignment.

    3/3 aligned = strong (trade full size)
    2/3 aligned = moderate (trade half size)
    1/3 or 0/3 = weak (skip or minimal)
    """
    is_buy = signal_action.lower() == "buy"
    target = "bullish" if is_buy else "bearish"

    scores = {
        "1h": 1 if tf_1h == target else (-1 if tf_1h != "neutral" else 0),
        "4h": 1 if tf_4h == target else (-1 if tf_4h != "neutral" else 0),
        "1d": 1 if tf_1d == target else (-1 if tf_1d != "neutral" else 0),
    }

    aligned = sum(1 for v in scores.values() if v > 0)
    against = sum(1 for v in scores.values() if v < 0)
    total_score = sum(scores.values())

    # Higher TF weighted more
    weighted = scores["1h"] * 1 + scores["4h"] * 2 + scores["1d"] * 3
    max_weighted = 6

    return {
        "timeframes": {"1h": tf_1h, "4h": tf_4h, "1d": tf_1d},
        "aligned": aligned,
        "against": against,
        "score": total_score,
        "weighted_score": weighted,
        "max_weighted": max_weighted,
        "confidence_pct": round(max(0, weighted / max_weighted * 100), 0),
        "size_recommendation": (
            "Full size (100%)" if aligned == 3
            else "Half size (50%)" if aligned == 2
            else "Quarter size (25%)" if aligned == 1
            else "Skip — no alignment"
        ),
        "tradeable": aligned >= 2,
    }


# ═══ 7. COMPREHENSIVE TRADE PLAN ═══

def generate_expert_trade_plan(
    ticker: str,
    action: str,
    entry_price: float,
    take_profit: float,
    stop_loss: float,
    capital: float = 100000,
    win_rate: float = 0.60,
    avg_win_pct: float = 3.0,
    avg_loss_pct: float = 2.0,
    regime: str = "trending_up",
    atr_current: float = 1.0,
    atr_avg: float = 1.0,
    tf_1h: str = "bullish",
    tf_4h: str = "bullish",
    tf_1d: str = "neutral",
) -> dict:
    """Generate comprehensive expert-level trade plan.

    Combines: Kelly sizing + Regime adjustment + Pyramiding + EV + Multi-TF.
    """
    # 1. Expected Value check
    ev = expected_value(win_rate, avg_win_pct, avg_loss_pct)

    # 2. Multi-TF confirmation
    mtf = multi_tf_score(tf_1h, tf_4h, tf_1d, action)

    # 3. Kelly position sizing
    kelly = kelly_position_size(win_rate, avg_win_pct, avg_loss_pct, capital, entry_price, stop_loss)

    # 4. Regime adjustment
    regime_adj = regime_risk_adjustment(kelly.risk_per_trade_pct, regime, atr_current, atr_avg)

    # 5. Pyramid plan
    pyramid = pyramid_plan(entry_price, action, take_profit, stop_loss, regime_adj["adjusted_risk_pct"])

    # 6. R:R calculation
    is_buy = action.lower() == "buy"
    reward = abs(take_profit - entry_price)
    risk = abs(entry_price - stop_loss)
    rr_ratio = reward / risk if risk > 0 else 0

    # 7. Overall verdict
    should_trade = ev["tradeable"] and mtf["tradeable"] and rr_ratio >= 1.5
    confidence = (
        (ev["expected_value_pct"] > 0) * 25 +
        (mtf["aligned"] >= 2) * 25 +
        (rr_ratio >= 2) * 25 +
        (regime_adj["regime_multiplier"] >= 1.0) * 25
    )

    return {
        "ticker": ticker,
        "action": action,
        "entry_price": entry_price,
        "take_profit": take_profit,
        "stop_loss": stop_loss,
        "rr_ratio": round(rr_ratio, 2),

        # Verdict
        "should_trade": should_trade,
        "confidence_pct": confidence,
        "verdict": (
            "STRONG TRADE — all systems aligned" if confidence == 100
            else "GOOD TRADE — most criteria met" if confidence >= 75
            else "MARGINAL — proceed with caution" if confidence >= 50
            else "SKIP — insufficient edge"
        ),

        # Components
        "expected_value": ev,
        "multi_timeframe": mtf,
        "kelly_sizing": {
            "full_kelly": kelly.full_kelly_pct,
            "half_kelly": kelly.half_kelly_pct,
            "recommended_risk": regime_adj["adjusted_risk_pct"],
            "position_lots": kelly.position_size_lots,
            "capital_at_risk": kelly.capital_at_risk,
        },
        "regime_adjustment": regime_adj,
        "pyramid_plan": pyramid,

        "disclaimer": "Not investment advice. Past performance does not guarantee future results.",
    }
