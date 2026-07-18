"""Connected-signals pipeline — messenger signals through the WEF engine.

Unifies both signal sources (TradingView webhook + Telegram parsing) into
one flow:

    raw signal
      -> AI rating (WEF Score)
      -> Evolutionary strategy check + correction (recommendation engine:
         regime-adjusted TP/SL, Kelly sizing, EV, strategy selection)
      -> Evolutionary verdict gate (SKIP => not broadcast)
      -> Quality gate (TP/SL, R:R, WEF, direction)
      -> Broadcast to VIP Telegram channel with full expert analysis
      -> Feed the evolutionary registry stats

Call `process_and_broadcast()` after a Signal row exists in the DB.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.provider import Provider
from app.models.signal import Signal
from app.services.ai_rating import ai_rating_service
from app.services.signal_quality import check_signal_quality
from app.services.telegram_bot import telegram_bot
from app.services.quant.recommendations import recommendation_engine

logger = logging.getLogger(__name__)

# Map recommendation verdict -> whether to broadcast
BROADCAST_VERDICTS = {"STRONG", "GOOD"}
# "MARGINAL" broadcasts with a warning; "SKIP" is dropped.


async def process_and_broadcast(
    db: AsyncSession,
    signal: Signal,
    provider: Provider | None = None,
    source: str = "telegram",
    apply_correction: bool = True,
) -> dict:
    """Run a saved Signal through the full WEF pipeline and broadcast to VIP.

    Returns a dict describing what happened (broadcast/skip + reasons).
    """
    result: dict = {"ticker": signal.ticker, "action": signal.action.value, "source": source}

    # Resolve provider if not passed
    if provider is None and signal.provider_id:
        provider = await db.get(Provider, signal.provider_id)

    # 1. AI rating -> WEF Score
    if settings.ai_rating_enabled and signal.ai_confidence is None:
        try:
            await ai_rating_service.rate_and_update_signal(db, signal)
            await db.refresh(signal)
        except Exception as e:
            logger.warning(f"AI rating failed for {signal.ticker}: {e}")
    result["wef"] = round((signal.ai_confidence or 0) * 100)

    # 2. Evolutionary strategy check + correction
    rec = {}
    expert = {}
    try:
        rec = await recommendation_engine.recommend(db, signal, provider)
        expert = rec.get("expert", {}) or {}
    except Exception as e:
        logger.warning(f"Recommendation engine failed for {signal.ticker}: {e}")

    verdict = expert.get("verdict", "")
    result["verdict"] = verdict

    # 3. Evolutionary verdict gate — SKIP means the strategy system rejects it
    if verdict == "SKIP" or expert.get("should_trade") is False:
        logger.info(f"Evolution rejected {signal.action.value} {signal.ticker} (verdict={verdict})")
        # Annotate the signal so it's visible why it wasn't broadcast
        signal.ai_reasoning = (signal.ai_reasoning or "") + f" | Evolution: SKIP"
        await db.commit()
        result["broadcast"] = False
        result["reason"] = "evolution_skip"
        return result

    # 4. Apply evolutionary corrections (regime-adjusted SL + calibrated TP)
    corrected_tp = signal.take_profit
    corrected_sl = signal.stop_loss
    if apply_correction and rec:
        # recommendation engine returns tp2 as the main target + regime-adjusted sl
        new_tp = rec.get("tp2")
        new_sl = rec.get("sl")
        if new_tp and new_sl:
            # Record the original before overwriting
            note = (
                f"Evolution corrected: TP {signal.take_profit}->{new_tp}, "
                f"SL {signal.stop_loss}->{new_sl} (regime={rec.get('regime')})"
            )
            signal.take_profit = round(float(new_tp), 6)
            signal.stop_loss = round(float(new_sl), 6)
            signal.ai_reasoning = (signal.ai_reasoning or "") + f" | {note}"
            await db.commit()
            await db.refresh(signal)
            corrected_tp = signal.take_profit
            corrected_sl = signal.stop_loss
            result["corrected"] = {"tp": corrected_tp, "sl": corrected_sl}

    # 5. Quality gate (after correction, so it judges the final levels)
    quality = await check_signal_quality(db, signal, provider)
    result["quality_tier"] = quality.tier
    if not quality.passed:
        logger.info(f"Quality gate blocked {signal.ticker}: {quality.issues}")
        signal.ai_reasoning = (signal.ai_reasoning or "") + f" | Quality: {quality.tier}"
        await db.commit()
        result["broadcast"] = False
        result["reason"] = "quality_gate"
        result["issues"] = quality.issues
        return result

    # 6. Broadcast to VIP with the evolutionary expert analysis
    expert_for_vip = {
        "verdict": verdict or quality.tier.upper(),
        "ev_per_trade_pct": expert.get("ev_per_trade_pct"),
        "profit_factor": expert.get("profit_factor"),
        "kelly_half_pct": expert.get("kelly_half_pct"),
        "regime_strategy": expert.get("regime_strategy"),
        "pyramid_levels": expert.get("pyramid_levels"),
        "edge_pct": expert.get("edge_pct"),
    }

    if telegram_bot.enabled and settings.telegram_vip_channel_id:
        try:
            await telegram_bot.broadcast_signal(
                signal.ticker, signal.action.value, signal.entry_price,
                signal.ai_confidence,
                tp=corrected_tp, sl=corrected_sl, expert=expert_for_vip,
            )
            result["broadcast"] = True
            logger.info(
                f"VIP broadcast [{source}]: {signal.action.value.upper()} {signal.ticker} "
                f"@ {signal.entry_price} WEF={result['wef']}% verdict={verdict}"
            )
        except Exception as e:
            logger.error(f"VIP broadcast failed for {signal.ticker}: {e}")
            result["broadcast"] = False
            result["reason"] = "broadcast_error"
    else:
        result["broadcast"] = False
        result["reason"] = "bot_disabled"
        logger.info(f"Bot disabled — would broadcast {signal.ticker} (WEF {result['wef']}%, {verdict})")

    # 7. Feed evolutionary registry stats (best-effort)
    try:
        from app.services.quant.evolution import evolutionary_registry
        strategy_id = expert.get("strategy_id") or 6  # risk-management branch default
        meta_score = (signal.ai_confidence or 0.5)
        evolutionary_registry.record_signal_evolution(
            strategy_id=strategy_id,
            meta_score=meta_score,
            regime=rec.get("regime", "unknown"),
            components_detected=["signal_quality_gate", "regime_strategy_selector"],
        )
    except Exception as e:
        logger.debug(f"Evolution stat record skipped: {e}")

    return result
