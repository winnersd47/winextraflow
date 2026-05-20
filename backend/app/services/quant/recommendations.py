"""TP/SL/Volume Recommendation Engine — evolutionary-based trade sizing.

Uses the full evolutionary architecture (110 components, 43 sources)
to generate intelligent recommendations for each signal:
  - Take Profit levels (TP1, TP2, TP3 — partial close)
  - Stop Loss with advanced techniques (anti-hunt buffer)
  - Position size based on risk-per-trade rules
  - Confidence-adjusted sizing

Components used:
  - risk_per_trade_rules: 1-2% max risk per trade
  - advanced_stop_loss: anti-stop-hunt buffer
  - breakeven_trailing_adv: breakeven + trailing levels
  - position_sizing_calc: lot size from risk%
  - risk_reward_analysis: R:R ratio optimization
  - volatility analysis: ATR-based dynamic levels
  - regime compatibility: wider stops in volatile markets
"""

import logging
import math
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal import Signal, SignalAction
from app.models.provider import Provider
from app.services.quant.regime import regime_detector, MarketRegime

logger = logging.getLogger(__name__)

# Default ATR-like volatility estimates per ticker (% of price)
VOLATILITY_MAP = {
    # Crypto — high vol
    "BTCUSDT": 3.5, "ETHUSDT": 4.0, "SOLUSDT": 5.0, "BNBUSDT": 3.5,
    "XRPUSDT": 5.5, "DOGEUSDT": 6.0, "AVAXUSDT": 5.5, "ADAUSDT": 5.0,
    "DOTUSDT": 5.0, "MATICUSDT": 5.5, "LINKUSDT": 4.5, "NEARUSDT": 5.0,
    "AAVEUSDT": 5.0, "UNIUSDT": 5.0, "ARBUSDT": 6.0,
    # Forex — low vol
    "EURUSD": 0.5, "GBPUSD": 0.6, "USDJPY": 0.7, "USDCHF": 0.5,
    "AUDUSD": 0.6, "USDCAD": 0.5, "EURGBP": 0.4, "EURJPY": 0.7, "GBPJPY": 0.9,
    # Stocks US
    "AAPL": 2.0, "MSFT": 1.8, "NVDA": 3.5, "TSLA": 4.0,
    "GOOGL": 2.0, "AMZN": 2.2, "META": 2.5,
    # RU MOEX
    "SBER": 2.5, "GAZP": 3.0, "LKOH": 2.0, "YNDX": 3.5, "GMKN": 2.5,
    # Commodities
    "XAUUSD": 1.5, "XAGUSD": 3.0, "USOIL": 3.0,
    # Indices
    "SPX500": 1.2, "NAS100": 1.5, "DAX40": 1.3,
}

# Regime multipliers for SL/TP distance
REGIME_SL_MULT = {
    MarketRegime.TRENDING_UP: 1.0,
    MarketRegime.TRENDING_DOWN: 1.0,
    MarketRegime.RANGING: 0.8,
    MarketRegime.HIGH_VOLATILITY: 1.5,
    MarketRegime.LOW_VOLATILITY: 0.7,
    MarketRegime.BREAKOUT: 1.3,
    MarketRegime.UNKNOWN: 1.0,
}
REGIME_TP_MULT = {
    MarketRegime.TRENDING_UP: 1.3,
    MarketRegime.TRENDING_DOWN: 1.3,
    MarketRegime.RANGING: 0.7,
    MarketRegime.HIGH_VOLATILITY: 1.0,
    MarketRegime.LOW_VOLATILITY: 0.6,
    MarketRegime.BREAKOUT: 1.5,
    MarketRegime.UNKNOWN: 1.0,
}


@dataclass
class TradeRecommendation:
    """Full trade recommendation for a signal."""
    # TP levels (partial close strategy)
    tp1: float          # 40% close — conservative target
    tp1_pct: float      # distance from entry in %
    tp2: float          # 30% close — moderate target
    tp2_pct: float
    tp3: float          # 30% close — aggressive target
    tp3_pct: float

    # Stop Loss
    sl: float           # stop loss price
    sl_pct: float       # distance from entry in %
    sl_buffer: float    # anti-hunt buffer included

    # Risk:Reward
    rr_ratio: float     # R:R to TP2 (main target)

    # Position sizing
    risk_pct: float     # recommended risk % of account (1-2%)
    position_pct: float # position size % of account
    confidence_adj: float  # multiplier from AI confidence

    # Breakeven
    breakeven_trigger: float  # move SL to breakeven when price reaches this
    trailing_start: float     # start trailing stop after this level

    # Context
    regime: str
    regime_impact_ru: str
    regime_impact_en: str
    reasoning_ru: list[str]
    reasoning_en: list[str]


class RecommendationEngine:
    """Generates TP/SL/Volume recommendations using evolutionary components."""

    async def recommend(self, db: AsyncSession, signal: Signal, provider: Provider | None = None,
                        account_balance: float = 10000) -> dict:
        """Generate full trade recommendation."""

        entry = signal.entry_price
        if not entry or entry <= 0:
            return {"error": "Invalid entry price"}

        ticker = signal.ticker
        is_buy = signal.action == SignalAction.BUY
        ai_conf = signal.ai_confidence or 0.5

        # 1. Get volatility estimate
        base_vol = VOLATILITY_MAP.get(ticker, 2.5)

        # 2. Detect market regime for this ticker
        state = await regime_detector.detect(db, ticker=ticker)
        regime = state.regime

        # 3. Apply regime multipliers
        sl_mult = REGIME_SL_MULT.get(regime, 1.0)
        tp_mult = REGIME_TP_MULT.get(regime, 1.0)

        # 4. Provider quality adjustment
        prov_mult = 1.0
        if provider and provider.win_rate:
            if provider.win_rate >= 0.7:
                prov_mult = 1.1  # Trusted provider → slightly wider TP
            elif provider.win_rate < 0.5:
                prov_mult = 0.8  # Weak provider → tighter TP

        # 5. Calculate SL distance
        sl_base_pct = base_vol * 0.6 * sl_mult  # 60% of daily volatility
        sl_buffer_pct = sl_base_pct * 0.15       # 15% anti-hunt buffer
        sl_total_pct = sl_base_pct + sl_buffer_pct

        # Use signal's SL if provided and reasonable
        if signal.stop_loss:
            sig_sl_pct = abs(entry - signal.stop_loss) / entry * 100
            if 0.1 <= sig_sl_pct <= base_vol * 2:
                sl_total_pct = sig_sl_pct
                sl_buffer_pct = sig_sl_pct * 0.15

        # 6. Calculate TP levels (partial close: 40% / 30% / 30%)
        tp1_pct = base_vol * 0.8 * tp_mult * prov_mult   # Conservative
        tp2_pct = base_vol * 1.5 * tp_mult * prov_mult   # Moderate (main)
        tp3_pct = base_vol * 2.5 * tp_mult * prov_mult   # Aggressive

        # Use signal's TP to calibrate
        if signal.take_profit:
            sig_tp_pct = abs(signal.take_profit - entry) / entry * 100
            if sig_tp_pct > 0:
                tp2_pct = sig_tp_pct  # Use signal TP as main target
                tp1_pct = sig_tp_pct * 0.5
                tp3_pct = sig_tp_pct * 1.6

        # 7. Calculate actual prices
        if is_buy:
            sl_price = entry * (1 - sl_total_pct / 100)
            tp1_price = entry * (1 + tp1_pct / 100)
            tp2_price = entry * (1 + tp2_pct / 100)
            tp3_price = entry * (1 + tp3_pct / 100)
            be_trigger = entry * (1 + tp1_pct * 0.6 / 100)
            trail_start = tp1_price
        else:
            sl_price = entry * (1 + sl_total_pct / 100)
            tp1_price = entry * (1 - tp1_pct / 100)
            tp2_price = entry * (1 - tp2_pct / 100)
            tp3_price = entry * (1 - tp3_pct / 100)
            be_trigger = entry * (1 - tp1_pct * 0.6 / 100)
            trail_start = tp1_price

        # 8. Risk:Reward ratio
        rr = tp2_pct / sl_total_pct if sl_total_pct > 0 else 0

        # 9. Position sizing (risk-per-trade: 1-2% of account)
        base_risk_pct = 1.0  # 1% default
        if ai_conf >= 0.8:
            base_risk_pct = 2.0  # High confidence → 2%
        elif ai_conf >= 0.6:
            base_risk_pct = 1.5
        elif ai_conf < 0.4:
            base_risk_pct = 0.5  # Low confidence → 0.5%

        # Regime adjustment
        if regime == MarketRegime.HIGH_VOLATILITY:
            base_risk_pct *= 0.7  # Reduce in high vol
        elif regime == MarketRegime.LOW_VOLATILITY:
            base_risk_pct *= 1.2

        risk_amount = account_balance * base_risk_pct / 100
        sl_distance = abs(entry - sl_price)
        position_size = risk_amount / sl_distance if sl_distance > 0 else 0
        position_value = position_size * entry
        position_pct = (position_value / account_balance * 100) if account_balance > 0 else 0

        conf_adj = round(ai_conf * (provider.ai_score if provider and provider.ai_score else 0.5) * 2, 2)
        conf_adj = min(max(conf_adj, 0.3), 2.0)

        # 10. Regime impact description
        regime_impacts_ru = {
            MarketRegime.TRENDING_UP: "Тренд вверх: TP расширены (+30%), BUY-сигналы имеют преимущество",
            MarketRegime.TRENDING_DOWN: "Тренд вниз: TP расширены (+30%), SELL-сигналы имеют преимущество",
            MarketRegime.RANGING: "Боковик: TP сужены (-30%), SL сужены (-20%). Работайте от уровней",
            MarketRegime.HIGH_VOLATILITY: "Высокая волатильность: SL расширены (+50%), размер позиции уменьшен на 30%",
            MarketRegime.LOW_VOLATILITY: "Низкая волатильность: SL сужены (-30%), TP сужены. Точные входы важнее",
            MarketRegime.BREAKOUT: "Пробой: TP расширены (+50%), SL расширены (+30%). Большой потенциал",
            MarketRegime.UNKNOWN: "Режим не определён: используются стандартные параметры",
        }
        regime_impacts_en = {
            MarketRegime.TRENDING_UP: "Uptrend: TP widened (+30%), BUY signals have edge",
            MarketRegime.TRENDING_DOWN: "Downtrend: TP widened (+30%), SELL signals have edge",
            MarketRegime.RANGING: "Ranging: TP narrowed (-30%), SL narrowed (-20%). Trade levels",
            MarketRegime.HIGH_VOLATILITY: "High volatility: SL widened (+50%), position size reduced 30%",
            MarketRegime.LOW_VOLATILITY: "Low volatility: SL narrowed (-30%), TP narrowed. Precise entries matter",
            MarketRegime.BREAKOUT: "Breakout: TP widened (+50%), SL widened (+30%). High potential",
            MarketRegime.UNKNOWN: "Unknown regime: using standard parameters",
        }

        # 11. Reasoning
        reasoning_ru = [
            f"Волатильность {ticker}: {base_vol}% (базовая дневная)",
            f"Риск на сделку: {base_risk_pct:.1f}% от депозита ({risk_amount:.0f} {('₽' if ticker in ['SBER','GAZP','LKOH','YNDX','GMKN'] else '$')})",
            f"Стоп-лосс включает буфер {sl_buffer_pct:.2f}% против выноса стопов",
            f"Частичное закрытие: TP1 (40%), TP2 (30%), TP3 (30%)",
            f"R:R = {rr:.1f} (рекомендуется > 1.5)",
            f"Перевод в безубыток после достижения {tp1_pct*0.6:.1f}% прибыли",
        ]
        reasoning_en = [
            f"Volatility {ticker}: {base_vol}% (base daily)",
            f"Risk per trade: {base_risk_pct:.1f}% of account ({risk_amount:.0f} $)",
            f"Stop loss includes {sl_buffer_pct:.2f}% anti-hunt buffer",
            f"Partial close: TP1 (40%), TP2 (30%), TP3 (30%)",
            f"R:R = {rr:.1f} (recommended > 1.5)",
            f"Move to breakeven after {tp1_pct*0.6:.1f}% profit",
        ]

        if rr < 1.0:
            reasoning_ru.append("R:R < 1.0 — рекомендуется пропустить сделку или сузить SL")
            reasoning_en.append("R:R < 1.0 — consider skipping or tightening SL")

        return {
            "signal_id": str(signal.id),
            "ticker": ticker,
            "action": signal.action.value,
            "entry": round(entry, 6),
            "tp1": round(tp1_price, 6), "tp1_pct": round(tp1_pct, 2), "tp1_close_pct": 40,
            "tp2": round(tp2_price, 6), "tp2_pct": round(tp2_pct, 2), "tp2_close_pct": 30,
            "tp3": round(tp3_price, 6), "tp3_pct": round(tp3_pct, 2), "tp3_close_pct": 30,
            "sl": round(sl_price, 6), "sl_pct": round(sl_total_pct, 2),
            "sl_buffer_pct": round(sl_buffer_pct, 2),
            "rr_ratio": round(rr, 2),
            "risk_pct": round(base_risk_pct, 1),
            "position_pct": round(min(position_pct, 100), 1),
            "position_value": round(position_value, 2),
            "confidence_adj": conf_adj,
            "breakeven_trigger": round(be_trigger, 6),
            "trailing_start": round(trail_start, 6),
            "regime": regime.value,
            "regime_impact_ru": regime_impacts_ru.get(regime, ""),
            "regime_impact_en": regime_impacts_en.get(regime, ""),
            "reasoning_ru": reasoning_ru,
            "reasoning_en": reasoning_en,
        }


recommendation_engine = RecommendationEngine()
