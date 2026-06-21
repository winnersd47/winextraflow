"""Top 1% Trading Strategies — institutional-grade algorithms.

Based on Renaissance Technologies / Medallion Fund principles:
1. Statistical Arbitrage (Pairs Trading with Cointegration)
2. Mean Reversion Z-Score System
3. Momentum + Trend Filtering (Dual Momentum)
4. Multi-Factor Scoring Model
5. Regime-Conditional Strategy Selector

Each strategy outputs: signal (buy/sell/hold), confidence, entry/exit, position size.
"""

import math
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ═══ 1. PAIRS TRADING (STATISTICAL ARBITRAGE) ═══

@dataclass
class PairsSignal:
    pair: str  # "SBER/GAZP"
    spread: float
    z_score: float
    action: str  # "long_spread", "short_spread", "exit", "hold"
    confidence: float
    entry_a: str  # "buy SBER"
    entry_b: str  # "sell GAZP"
    stop_z: float
    target_z: float


def pairs_trading_signal(
    prices_a: list[float],
    prices_b: list[float],
    ticker_a: str = "A",
    ticker_b: str = "B",
    lookback: int = 60,
    entry_z: float = 2.0,
    exit_z: float = 0.5,
    stop_z: float = 3.0,
) -> PairsSignal:
    """Pairs trading: cointegration-based mean reversion.

    1. Calculate spread = log(A) - beta * log(B)
    2. Compute Z-score of spread
    3. Entry at |Z| > entry_z, exit at |Z| < exit_z, stop at |Z| > stop_z
    """
    if len(prices_a) < lookback or len(prices_b) < lookback:
        return PairsSignal(f"{ticker_a}/{ticker_b}", 0, 0, "hold", 0, "", "", 0, 0)

    # Use recent window
    pa = prices_a[-lookback:]
    pb = prices_b[-lookback:]

    # Log prices
    log_a = [math.log(p) for p in pa if p > 0]
    log_b = [math.log(p) for p in pb if p > 0]
    n = min(len(log_a), len(log_b))
    log_a = log_a[:n]
    log_b = log_b[:n]

    # OLS regression: log_a = alpha + beta * log_b
    mean_a = sum(log_a) / n
    mean_b = sum(log_b) / n
    cov = sum((log_a[i] - mean_a) * (log_b[i] - mean_b) for i in range(n)) / n
    var_b = sum((log_b[i] - mean_b) ** 2 for i in range(n)) / n
    beta = cov / var_b if var_b > 0 else 1.0
    alpha = mean_a - beta * mean_b

    # Spread = log(A) - beta * log(B)
    spreads = [log_a[i] - beta * log_b[i] for i in range(n)]
    spread_mean = sum(spreads) / n
    spread_std = math.sqrt(sum((s - spread_mean) ** 2 for s in spreads) / n)

    current_spread = spreads[-1]
    z_score = (current_spread - spread_mean) / spread_std if spread_std > 0 else 0

    # Signal generation
    if z_score > entry_z:
        action = "short_spread"  # spread too high → short A, long B
        entry_a = f"SELL {ticker_a}"
        entry_b = f"BUY {ticker_b}"
        confidence = min(abs(z_score) / stop_z, 1.0)
    elif z_score < -entry_z:
        action = "long_spread"  # spread too low → long A, short B
        entry_a = f"BUY {ticker_a}"
        entry_b = f"SELL {ticker_b}"
        confidence = min(abs(z_score) / stop_z, 1.0)
    elif abs(z_score) < exit_z:
        action = "exit"
        entry_a = f"Close {ticker_a}"
        entry_b = f"Close {ticker_b}"
        confidence = 1.0 - abs(z_score)
    else:
        action = "hold"
        entry_a = ""
        entry_b = ""
        confidence = 0

    return PairsSignal(
        pair=f"{ticker_a}/{ticker_b}",
        spread=round(current_spread, 6),
        z_score=round(z_score, 3),
        action=action,
        confidence=round(confidence, 3),
        entry_a=entry_a,
        entry_b=entry_b,
        stop_z=stop_z,
        target_z=exit_z,
    )


# ═══ 2. MEAN REVERSION Z-SCORE SYSTEM ═══

def mean_reversion_signal(
    prices: list[float],
    lookback: int = 20,
    entry_z: float = 2.0,
    exit_z: float = 0.5,
    stop_z: float = 3.0,
) -> dict:
    """Single-asset mean reversion using Z-score of price vs SMA.

    Buy when price is 2σ below mean, sell when 2σ above.
    """
    if len(prices) < lookback:
        return {"action": "hold", "z_score": 0, "confidence": 0}

    window = prices[-lookback:]
    mean = sum(window) / lookback
    std = math.sqrt(sum((p - mean) ** 2 for p in window) / lookback)
    current = prices[-1]
    z = (current - mean) / std if std > 0 else 0

    if z < -entry_z:
        action = "buy"
        confidence = min(abs(z) / stop_z, 1.0)
    elif z > entry_z:
        action = "sell"
        confidence = min(abs(z) / stop_z, 1.0)
    elif abs(z) < exit_z:
        action = "exit"
        confidence = 0.5
    else:
        action = "hold"
        confidence = 0

    return {
        "action": action,
        "z_score": round(z, 3),
        "mean": round(mean, 4),
        "std": round(std, 4),
        "current": current,
        "deviation_pct": round((current - mean) / mean * 100, 2),
        "confidence": round(confidence, 3),
        "entry_z": entry_z,
        "stop_z": stop_z,
    }


# ═══ 3. DUAL MOMENTUM (TREND + ABSOLUTE) ═══

def dual_momentum_signal(
    prices: list[float],
    benchmark_prices: list[float],
    lookback: int = 60,  # ~3 months
    risk_free_rate_annual: float = 0.05,
) -> dict:
    """Dual Momentum: Relative + Absolute momentum filter.

    1. Relative momentum: asset vs benchmark (which is stronger?)
    2. Absolute momentum: is asset trending up at all?
    3. Only go long if BOTH are positive
    """
    if len(prices) < lookback or len(benchmark_prices) < lookback:
        return {"action": "hold", "confidence": 0}

    # Returns over lookback
    asset_return = (prices[-1] / prices[-lookback] - 1) * 100
    bench_return = (benchmark_prices[-1] / benchmark_prices[-lookback] - 1) * 100
    rf_return = risk_free_rate_annual / 12 * (lookback / 20) * 100  # approximate

    # Relative momentum: asset vs benchmark
    relative = asset_return - bench_return

    # Absolute momentum: asset vs risk-free
    absolute = asset_return - rf_return

    # Signal
    if relative > 0 and absolute > 0:
        action = "buy"
        confidence = min((relative + absolute) / 20, 1.0)
        reason = f"Asset +{asset_return:.1f}% vs bench +{bench_return:.1f}% — dual momentum confirmed"
    elif absolute > 0:
        action = "hold"
        confidence = 0.3
        reason = f"Absolute momentum positive (+{absolute:.1f}%) but relative negative"
    else:
        action = "sell"
        confidence = min(abs(absolute) / 10, 1.0)
        reason = f"Absolute momentum negative ({absolute:.1f}%) — exit to cash/bonds"

    # Trend strength (SMA slope)
    sma_20 = sum(prices[-20:]) / 20
    sma_60 = sum(prices[-60:]) / min(60, len(prices))
    trend = "uptrend" if sma_20 > sma_60 else "downtrend"

    return {
        "action": action,
        "confidence": round(confidence, 3),
        "asset_return_pct": round(asset_return, 2),
        "benchmark_return_pct": round(bench_return, 2),
        "relative_momentum": round(relative, 2),
        "absolute_momentum": round(absolute, 2),
        "trend": trend,
        "sma_20": round(sma_20, 4),
        "sma_60": round(sma_60, 4),
        "reason": reason,
    }


# ═══ 4. MULTI-FACTOR SCORING MODEL ═══

def multi_factor_score(
    momentum_1m: float,  # 1-month return %
    momentum_3m: float,  # 3-month return %
    volatility: float,  # current volatility (ATR/price %)
    volume_ratio: float,  # current volume / avg volume
    rsi: float,  # RSI 14
    distance_from_sma200: float,  # % above/below 200 SMA
) -> dict:
    """Multi-factor scoring: Renaissance-style composite signal.

    6 factors → normalized score 0-100 → action.
    """
    scores = {}

    # Momentum (higher = better for long)
    scores["momentum_1m"] = min(max(momentum_1m / 5 + 50, 0), 100)
    scores["momentum_3m"] = min(max(momentum_3m / 10 + 50, 0), 100)

    # Volatility (lower = better, but not too low)
    if volatility < 0.5:
        scores["volatility"] = 40  # too low = no opportunity
    elif volatility < 2:
        scores["volatility"] = 80  # sweet spot
    elif volatility < 4:
        scores["volatility"] = 60
    else:
        scores["volatility"] = 30  # too high = risky

    # Volume (higher = better confirmation)
    scores["volume"] = min(volume_ratio * 50, 100)

    # RSI (mean reversion zones)
    if rsi < 30:
        scores["rsi"] = 85  # oversold = buy
    elif rsi < 40:
        scores["rsi"] = 70
    elif rsi < 60:
        scores["rsi"] = 50  # neutral
    elif rsi < 70:
        scores["rsi"] = 40
    else:
        scores["rsi"] = 20  # overbought = don't buy

    # Distance from SMA200
    if distance_from_sma200 > 0:
        scores["sma200"] = min(60 + distance_from_sma200, 90)  # above = bullish
    else:
        scores["sma200"] = max(50 + distance_from_sma200, 10)  # below = bearish

    # Weighted composite
    weights = {"momentum_1m": 0.20, "momentum_3m": 0.25, "volatility": 0.10, "volume": 0.15, "rsi": 0.15, "sma200": 0.15}
    composite = sum(scores[k] * weights[k] for k in weights)

    if composite >= 70:
        action = "strong_buy"
    elif composite >= 55:
        action = "buy"
    elif composite >= 45:
        action = "hold"
    elif composite >= 35:
        action = "sell"
    else:
        action = "strong_sell"

    return {
        "composite_score": round(composite, 1),
        "action": action,
        "factors": {k: round(v, 1) for k, v in scores.items()},
        "weights": weights,
        "confidence": round(abs(composite - 50) / 50, 3),
    }


# ═══ 5. REGIME-CONDITIONAL STRATEGY SELECTOR ═══

def select_strategy(
    regime: str,
    volatility: str,  # "low", "medium", "high"
    trend_strength: float,  # 0-1
) -> dict:
    """Select optimal strategy based on current market conditions.

    Trending + Low Vol → Trend Following / Momentum
    Trending + High Vol → Breakout with tight stops
    Ranging + Low Vol → Mean Reversion / Pairs Trading
    Ranging + High Vol → Reduce size or sit out
    """
    matrix = {
        ("trending_up", "low"): {"strategy": "Dual Momentum", "size": 1.0, "sl_mult": 1.0},
        ("trending_up", "medium"): {"strategy": "Trend Following + Pyramiding", "size": 0.8, "sl_mult": 1.2},
        ("trending_up", "high"): {"strategy": "Breakout with Trailing Stop", "size": 0.5, "sl_mult": 1.5},
        ("trending_down", "low"): {"strategy": "Short Momentum", "size": 0.8, "sl_mult": 1.0},
        ("trending_down", "medium"): {"strategy": "Mean Reversion (oversold bounce)", "size": 0.6, "sl_mult": 1.3},
        ("trending_down", "high"): {"strategy": "Cash / Hedge", "size": 0.2, "sl_mult": 2.0},
        ("ranging", "low"): {"strategy": "Pairs Trading / StatArb", "size": 1.0, "sl_mult": 0.8},
        ("ranging", "medium"): {"strategy": "Mean Reversion Z-Score", "size": 0.7, "sl_mult": 1.0},
        ("ranging", "high"): {"strategy": "Reduce All Positions", "size": 0.3, "sl_mult": 1.5},
        ("breakout", "low"): {"strategy": "Breakout Confirmation + Volume", "size": 0.9, "sl_mult": 1.0},
        ("breakout", "medium"): {"strategy": "Breakout + Anti-Martingale", "size": 0.7, "sl_mult": 1.2},
        ("breakout", "high"): {"strategy": "Breakout with Wide Stop", "size": 0.4, "sl_mult": 2.0},
    }

    key = (regime, volatility)
    selected = matrix.get(key, {"strategy": "Conservative / Cash", "size": 0.3, "sl_mult": 1.5})

    return {
        "regime": regime,
        "volatility": volatility,
        "trend_strength": round(trend_strength, 2),
        "recommended_strategy": selected["strategy"],
        "position_size_multiplier": selected["size"],
        "stop_loss_multiplier": selected["sl_mult"],
        "rationale": f"{regime} + {volatility} volatility → {selected['strategy']}",
    }
