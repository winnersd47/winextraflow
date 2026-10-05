"""MT5 Bridge — WebSocket server for MetaTrader 5 integration with LLM.

Architecture:
  MT5 Terminal (MQL5) → WebSocket (127.0.0.1:8765) → Python Server → OpenRouter LLM
  MT5 Terminal ← Trade commands ← AI Decision + Signal

Solves three bottlenecks:
1. Blocking requests in MQL5 — async WebSocket, MT5 just sends/receives JSON
2. Rate limits — BATCH mode with ThreadPoolExecutor, queue + debounce
3. API key security — keys stay in Python .env, never in MQL5 code

Transport: WebSocket via asyncio (primary) + TCP fallback
LLM: OpenRouter API (swap provider in one line)
"""

import asyncio
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import httpx
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

# ═══ CONFIG ═══

WS_HOST = "127.0.0.1"
WS_PORT = 8765
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# settings first (.env is loaded there), env var as an override
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "") or settings.openrouter_api_key
LLM_MODEL = os.getenv("LLM_MODEL", "") or settings.llm_model
MAX_BATCH_SIZE = 10
BATCH_TIMEOUT = 2.0  # seconds to wait for batch to fill
RATE_LIMIT_DELAY = 0.5  # seconds between LLM calls

# Every LLM command is billed to the platform's own OpenRouter key, so an
# unauthenticated listener is an open LLM proxy. Loopback-only is safe; any other
# bind address requires a shared secret that the MQL5 side sends in `auth`.
BRIDGE_TOKEN = settings.mt5_bridge_token
LOOPBACK = {"127.0.0.1", "::1", "localhost"}
# Per-connection budget: an EA on a 15-minute chart needs a handful of calls, not
# hundreds. Stops one misbehaving or hijacked client draining the key.
MAX_LLM_CALLS_PER_CONN = 120
MAX_LLM_CALLS_WINDOW_SEC = 3600

executor = ThreadPoolExecutor(max_workers=4)


class BridgeAuthError(Exception):
    """Raised when a client fails the shared-secret check."""


# ═══ INDICATORS (NumPy-based, fast) ═══

def calc_indicators(candles: list[dict]) -> dict:
    """Calculate technical indicators from OHLCV candles using NumPy."""
    if len(candles) < 20:
        return {"error": "Need at least 20 candles"}

    closes = np.array([c["close"] for c in candles], dtype=float)
    highs = np.array([c["high"] for c in candles], dtype=float)
    lows = np.array([c["low"] for c in candles], dtype=float)
    volumes = np.array([c.get("volume", 0) for c in candles], dtype=float)

    # SMA
    sma20 = np.mean(closes[-20:])
    sma50 = np.mean(closes[-min(50, len(closes)):])

    # EMA 12, 26
    def ema(data, period):
        alpha = 2 / (period + 1)
        result = np.zeros_like(data)
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
        return result

    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    macd = ema12 - ema26
    macd_signal = ema(macd, 9)
    macd_hist = macd - macd_signal

    # RSI 14
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[-14:])
    avg_loss = np.mean(losses[-14:])
    rs = avg_gain / avg_loss if avg_loss > 0 else 100
    rsi = 100 - 100 / (1 + rs)

    # ATR 14
    tr_vals = []
    for i in range(-14, 0):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        tr_vals.append(tr)
    atr = np.mean(tr_vals)

    # Bollinger Bands
    bb_mean = sma20
    bb_std = np.std(closes[-20:])
    bb_upper = bb_mean + 2 * bb_std
    bb_lower = bb_mean - 2 * bb_std

    # Volume ratio
    vol_avg = np.mean(volumes[-20:]) if np.any(volumes) else 1
    vol_ratio = volumes[-1] / vol_avg if vol_avg > 0 else 1

    # Trend
    trend = "uptrend" if sma20 > sma50 else "downtrend" if sma20 < sma50 else "ranging"
    change_20d = (closes[-1] - closes[-20]) / closes[-20] * 100

    return {
        "price": float(closes[-1]),
        "sma20": round(float(sma20), 6),
        "sma50": round(float(sma50), 6),
        "ema12": round(float(ema12[-1]), 6),
        "ema26": round(float(ema26[-1]), 6),
        "macd": round(float(macd[-1]), 6),
        "macd_signal": round(float(macd_signal[-1]), 6),
        "macd_hist": round(float(macd_hist[-1]), 6),
        "rsi": round(float(rsi), 1),
        "atr": round(float(atr), 6),
        "atr_pct": round(float(atr / closes[-1] * 100), 2),
        "bb_upper": round(float(bb_upper), 6),
        "bb_lower": round(float(bb_lower), 6),
        "bb_mean": round(float(bb_mean), 6),
        "volume_ratio": round(float(vol_ratio), 2),
        "trend": trend,
        "change_20d": round(float(change_20d), 2),
    }


# ═══ LLM ANALYSIS ═══

async def llm_analyze(ticker: str, indicators: dict, timeframe: str = "H1") -> dict:
    """Send indicators to LLM via OpenRouter, get trade decision.

    Returns: {action, confidence, tp, sl, reasoning}
    """
    if not OPENROUTER_KEY:
        return _fallback_classify(ticker, indicators)

    prompt = f"""You are a professional quantitative trader. Analyze this data and give a trading decision.

Ticker: {ticker}
Timeframe: {timeframe}
Current Price: {indicators['price']}

Technical Indicators:
- SMA20: {indicators['sma20']} | SMA50: {indicators['sma50']} | Trend: {indicators['trend']}
- RSI(14): {indicators['rsi']}
- MACD: {indicators['macd']} | Signal: {indicators['macd_signal']} | Histogram: {indicators['macd_hist']}
- ATR(14): {indicators['atr']} ({indicators['atr_pct']}%)
- Bollinger: Upper {indicators['bb_upper']} | Lower {indicators['bb_lower']}
- Volume Ratio: {indicators['volume_ratio']}x average
- 20-day Change: {indicators['change_20d']}%

Respond ONLY with valid JSON (no markdown, no explanation outside JSON):
{{"action": "buy" or "sell" or "hold", "confidence": 0.0-1.0, "tp": price_number, "sl": price_number, "reasoning": "one sentence"}}"""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": LLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0.1,
                },
            )
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Strict JSON parsing
            result = json.loads(content)
            if result.get("action") not in ("buy", "sell", "hold"):
                raise ValueError(f"Invalid action: {result.get('action')}")
            return result

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning(f"LLM parse failed for {ticker}: {e}, falling back to keyword classification")
        return _fallback_classify(ticker, indicators)
    except Exception as e:
        logger.error(f"LLM request failed for {ticker}: {e}")
        return _fallback_classify(ticker, indicators)


def _fallback_classify(ticker: str, ind: dict) -> dict:
    """Fallback classification by keywords/rules when LLM unavailable."""
    price = ind["price"]
    rsi = ind["rsi"]
    trend = ind["trend"]
    macd_hist = ind["macd_hist"]
    atr = ind["atr"]

    # Rule-based decision
    if trend == "uptrend" and rsi < 70 and macd_hist > 0:
        action = "buy"
        confidence = 0.7
        tp = round(price + atr * 3, 6)
        sl = round(price - atr * 1.5, 6)
        reasoning = f"Uptrend confirmed: SMA20>SMA50, RSI={rsi:.0f}, MACD histogram positive"
    elif trend == "downtrend" and rsi > 30 and macd_hist < 0:
        action = "sell"
        confidence = 0.7
        tp = round(price - atr * 3, 6)
        sl = round(price + atr * 1.5, 6)
        reasoning = f"Downtrend confirmed: SMA20<SMA50, RSI={rsi:.0f}, MACD histogram negative"
    elif rsi < 25:
        action = "buy"
        confidence = 0.55
        tp = round(price + atr * 2, 6)
        sl = round(price - atr * 1.5, 6)
        reasoning = f"Oversold: RSI={rsi:.0f}, expecting mean reversion bounce"
    elif rsi > 75:
        action = "sell"
        confidence = 0.55
        tp = round(price - atr * 2, 6)
        sl = round(price + atr * 1.5, 6)
        reasoning = f"Overbought: RSI={rsi:.0f}, expecting pullback"
    else:
        action = "hold"
        confidence = 0.3
        tp = price
        sl = price
        reasoning = f"No clear signal: RSI={rsi:.0f}, trend={trend}, MACD inconclusive"

    return {"action": action, "confidence": confidence, "tp": tp, "sl": sl, "reasoning": reasoning}


# ═══ BATCH PROCESSING ═══

_batch_queue: list[dict] = []
_batch_lock = asyncio.Lock()


async def process_batch(items: list[dict]) -> list[dict]:
    """Process multiple tickers in parallel with rate limiting."""
    results = []
    for i, item in enumerate(items):
        if i > 0:
            await asyncio.sleep(RATE_LIMIT_DELAY)

        ticker = item.get("ticker", "")
        candles = item.get("candles", [])
        timeframe = item.get("timeframe", "H1")

        indicators = calc_indicators(candles)
        if "error" in indicators:
            results.append({"ticker": ticker, "error": indicators["error"]})
            continue

        decision = await llm_analyze(ticker, indicators, timeframe)
        decision["ticker"] = ticker
        decision["indicators"] = indicators
        results.append(decision)

    return results


# ═══ WEBSOCKET SERVER ═══

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Handle TCP connection from MT5."""
    addr = writer.get_extra_info("peername")
    logger.info(f"MT5 connected: {addr}")
    llm_calls = 0
    window_start = time.monotonic()

    try:
        while True:
            data = await asyncio.wait_for(reader.readline(), timeout=60)
            if not data:
                break

            try:
                msg = json.loads(data.decode("utf-8").strip())
            except json.JSONDecodeError:
                writer.write(json.dumps({"error": "Invalid JSON"}).encode() + b"\n")
                await writer.drain()
                continue

            cmd = msg.get("cmd", "")

            # Shared secret, checked per message so a reconnect cannot skip it.
            if BRIDGE_TOKEN and not _token_ok(msg.get("auth", "")):
                logger.warning(f"MT5 auth failed from {addr}")
                writer.write(json.dumps({"error": "Unauthorized"}).encode() + b"\n")
                await writer.drain()
                break

            # Budget only the commands that cost money; ping/indicators are free.
            if cmd in ("analyze", "batch", "signal"):
                if time.monotonic() - window_start > MAX_LLM_CALLS_WINDOW_SEC:
                    llm_calls, window_start = 0, time.monotonic()
                cost = len(msg.get("items", [])[:MAX_BATCH_SIZE]) if cmd == "batch" else 1
                if llm_calls + cost > MAX_LLM_CALLS_PER_CONN:
                    writer.write(json.dumps({
                        "error": "Rate limit: LLM budget for this connection exhausted",
                        "retry_after_sec": int(MAX_LLM_CALLS_WINDOW_SEC -
                                               (time.monotonic() - window_start)),
                    }).encode() + b"\n")
                    await writer.drain()
                    continue
                llm_calls += cost

            if cmd == "analyze":
                # Single ticker analysis
                candles = msg.get("candles", [])
                ticker = msg.get("ticker", "UNKNOWN")
                tf = msg.get("timeframe", "H1")

                indicators = calc_indicators(candles)
                if "error" in indicators:
                    response = {"error": indicators["error"]}
                else:
                    response = await llm_analyze(ticker, indicators, tf)
                    response["ticker"] = ticker
                    response["indicators"] = indicators

            elif cmd == "signal":
                # Same analysis as "analyze", but the decision is stored as a
                # platform Signal and run through the standard pipeline (rating,
                # quality gate, publication) instead of ending at a terminal Alert.
                response = await _handle_signal(msg)

            elif cmd == "batch":
                # Batch analysis (multiple tickers)
                items = msg.get("items", [])[:MAX_BATCH_SIZE]
                response = {"results": await process_batch(items)}

            elif cmd == "indicators":
                # Just calculate indicators, no LLM
                candles = msg.get("candles", [])
                response = calc_indicators(candles)

            elif cmd == "ping":
                response = {"pong": True, "time": datetime.now(timezone.utc).isoformat()}

            else:
                response = {"error": f"Unknown command: {cmd}"}

            writer.write(json.dumps(response).encode() + b"\n")
            await writer.drain()

    except asyncio.TimeoutError:
        logger.info(f"MT5 timeout: {addr}")
    except Exception as e:
        logger.error(f"MT5 error: {e}")
    finally:
        writer.close()
        await writer.wait_closed()
        logger.info(f"MT5 disconnected: {addr}")


async def _handle_signal(msg: dict) -> dict:
    """Analyse, then store the decision as a platform Signal.

    "hold" is not stored: a decision not to trade is not a signal, and recording it
    would put rows with no levels into the same table the track record counts.
    """
    candles = msg.get("candles", [])
    symbol = msg.get("ticker") or msg.get("symbol") or "UNKNOWN"
    tf = msg.get("timeframe", "H1")

    indicators = calc_indicators(candles)
    if "error" in indicators:
        return {"error": indicators["error"]}

    decision = await llm_analyze(symbol, indicators, tf)
    action = (decision.get("action") or "").lower()
    if action not in ("buy", "sell"):
        return {"stored": False, "action": action or "hold",
                "reason": "hold — не сделка, не сохраняем",
                "confidence": decision.get("confidence"),
                "indicators": indicators}

    # The terminal's own last close is the entry reference: it is the price the
    # trade would actually be opened at, unlike a quote from another feed.
    price = indicators.get("price") or 0

    from app.database import async_session
    from app.services.mt5_signals import ingest
    async with async_session() as db:
        out = await ingest(
            db, symbol=symbol, action=action, price=price,
            tp=decision.get("tp"), sl=decision.get("sl"),
            confidence=float(decision.get("confidence") or 0),
            reasoning=decision.get("reasoning", ""),
            indicators=indicators, timeframe=tf,
        )
    out["indicators"] = indicators
    out["model_confidence"] = decision.get("confidence")
    return out


def _token_ok(supplied: str) -> bool:
    """Constant-time comparison of the shared secret."""
    import hmac
    return hmac.compare_digest(str(supplied), BRIDGE_TOKEN)


async def start_mt5_server(host: str = WS_HOST, port: int = WS_PORT):
    """Start TCP server for MT5 connections.

    Refuses to listen on anything but loopback without a token: the bridge spends
    the platform's LLM key on every `analyze` command, so an open port is an open
    wallet. Set MT5_BRIDGE_TOKEN and put the same value in the EA's inputs.
    """
    if host not in LOOPBACK and not BRIDGE_TOKEN:
        raise BridgeAuthError(
            f"Refusing to bind {host}:{port} without MT5_BRIDGE_TOKEN — the bridge "
            f"spends the OpenRouter key on every request and has no other access "
            f"control. Set MT5_BRIDGE_TOKEN in .env (and in the EA), or bind 127.0.0.1."
        )
    server = await asyncio.start_server(handle_client, host, port)
    auth = "token required" if BRIDGE_TOKEN else "loopback only, no token"
    logger.info(f"MT5 Bridge started on {host}:{port} ({auth})")
    async with server:
        await server.serve_forever()
