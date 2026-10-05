"""Turn an MT5 bridge decision into a platform signal.

The bridge used to end at an Alert in the terminal: nothing reached the database,
so nothing was rated, gated, published or measured. This is the missing half.

There is deliberately no parallel path. An MT5 signal goes through exactly what a
Telegram signal goes through — resolve_levels, ai_rating, check_signal_quality,
process_and_broadcast — and if it fails the seven checks it is not published, same
as any other. A second, more permissive route for our own signals is how a platform
ends up trusting its own output more than its sources'.

Two things are specific to this source:

  * the ATR comes from the terminal's own candles, so it is passed through rather
    than refetched. Sizing a stop off a different price feed than the one the trade
    executes against is a silent mismatch.
  * the model's `confidence` is recorded but is NOT a trade trigger. It is a number
    the model assigns itself after looking at five indicators, and nobody has
    checked that 0.7 means seven wins in ten. It enters the WEF Score as one factor;
    the decision to publish belongs to the quality gate.
"""

import logging
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import Provider, ProviderSource
from app.models.signal import Signal, SignalAction

logger = logging.getLogger(__name__)

PROVIDER_NAME = "MT5 Bridge"

# Brokers decorate symbols: EURUSD.m, EURUSDm, GBPUSD-ECN, XAUUSD.raw. The platform
# resolves prices by bare symbol, and an unrecognised ticker silently yields no
# candles — no chart, no ATR, no TP/SL monitoring (see BR-8.26, ZIL/BTC).
_SUFFIX_RE = re.compile(r"[.\-_](?:m|micro|ecn|raw|pro|std|c|cent|sml)$", re.IGNORECASE)
_TRAILING_LETTER_RE = re.compile(r"^([A-Z]{6})[a-z]$")

# MT5 metal/index names -> what backtesting_real can actually price.
SYMBOL_MAP = {
    "GOLD": "XAUUSD", "SILVER": "XAGUSD",
    "BTCUSD": "BTCUSDT", "ETHUSD": "ETHUSDT",
}


def normalize_symbol(symbol: str) -> str:
    """Strip broker decoration and map aliases to platform tickers."""
    s = (symbol or "").strip()
    s = _SUFFIX_RE.sub("", s)
    m = _TRAILING_LETTER_RE.match(s)
    if m:
        s = m.group(1)
    s = s.upper()
    return SYMBOL_MAP.get(s, s)


async def get_or_create_provider(db: AsyncSession) -> Provider:
    """The MT5 bridge as a real provider — not seeded, so it counts in rankings."""
    p = (await db.execute(
        select(Provider).where(Provider.name == PROVIDER_NAME).limit(1)
    )).scalar_one_or_none()
    if p:
        return p
    p = Provider(
        name=PROVIDER_NAME,
        source=ProviderSource.MT5,
        description="Сигналы из терминала MetaTrader 5: индикаторы + LLM через мост",
        is_active=True,
        is_seed=False,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    logger.info(f"Provider created: {PROVIDER_NAME}")
    return p


async def ingest(db: AsyncSession, symbol: str, action: str, price: float,
                 tp: float | None, sl: float | None, confidence: float,
                 reasoning: str = "", indicators: dict | None = None,
                 timeframe: str = "H1", broadcast: bool = True) -> dict:
    """Save one bridge decision as a Signal and run the standard pipeline.

    Returns what happened, in a shape the EA can print to the terminal log.
    """
    from app.services.signal_levels import resolve_levels
    from app.services.signal_pipeline import process_and_broadcast

    if (action or "").lower() not in ("buy", "sell"):
        return {"stored": False, "reason": f"action={action!r} is not tradable"}
    if not price or price <= 0:
        return {"stored": False, "reason": "no entry price"}

    ticker = normalize_symbol(symbol)
    if not ticker:
        return {"stored": False, "reason": "empty symbol"}

    indicators = indicators or {}
    # atr_pct arrives as a percentage from the bridge; resolve_levels wants a fraction.
    atr_frac = None
    if indicators.get("atr_pct"):
        try:
            atr_frac = float(indicators["atr_pct"]) / 100
        except (TypeError, ValueError):
            atr_frac = None

    lv = await resolve_levels(ticker, action, price, tp, sl, atr_override=atr_frac)
    if not lv["usable"]:
        return {"stored": False, "ticker": ticker, "reason": "no usable entry price"}

    provider = await get_or_create_provider(db)

    # The model's own words and readings, kept for the signal card. `confidence` is
    # recorded here as the model's self-assessment, explicitly labelled as such.
    parts = [f"MT5 {timeframe}"]
    if indicators:
        parts.append(
            "RSI {rsi} · MACD {macd} · ATR {atr_pct}%".format(
                rsi=indicators.get("rsi", "—"),
                macd=indicators.get("macd_hist", indicators.get("macd", "—")),
                atr_pct=indicators.get("atr_pct", "—"),
            )
        )
    parts.append(f"самооценка модели {confidence:.0%}")
    if reasoning:
        parts.append(reasoning.strip())
    raw = " | ".join(parts)

    signal = Signal(
        provider_id=provider.id,
        ticker=ticker,
        action=SignalAction(action.lower()),
        entry_price=lv["entry"],
        take_profit=lv["take_profit"],
        stop_loss=lv["stop_loss"],
        long_target=lv["long_target"],
        timeframe=timeframe,
        source_confidence=round(float(confidence), 4) if confidence else None,
        raw_message=raw[:500],
    )
    db.add(signal)
    provider.total_signals = (provider.total_signals or 0) + 1
    await db.commit()
    await db.refresh(signal)

    out = {
        "stored": True,
        "signal_id": str(signal.id),
        "ticker": ticker,
        "action": action.lower(),
        "entry": lv["entry"],
        "tp": lv["take_profit"],
        "sl": lv["stop_loss"],
        "notes": lv["notes"],
    }

    if not broadcast:
        return out

    try:
        outcome = await process_and_broadcast(db, signal, provider, source="mt5")
        await db.refresh(signal)
        out["wef"] = round((signal.ai_confidence or 0) * 100)
        out["verdict"] = outcome.get("verdict", "")
        out["published"] = bool(outcome.get("broadcast"))
        out["reason"] = outcome.get("reason", "")
    except Exception as e:
        # A failure here must not lose the signal: it is already stored and will be
        # picked up by the monitor and the paper accounts regardless.
        logger.error(f"MT5 pipeline failed for {ticker}: {e}")
        out["published"] = False
        out["reason"] = f"pipeline error: {e}"
    return out
