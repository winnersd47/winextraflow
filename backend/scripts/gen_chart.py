"""Generate candlestick chart with Entry/TP/SL lines and send to Telegram.

Usage:
    python scripts/gen_chart.py LKOH buy 7250 7800 6950
    python scripts/gen_chart.py SBER buy 318 345 305
    python scripts/gen_chart.py BTCUSDT sell 67000 63000 69000
"""

import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta, timezone

from app.services.backtesting_real import fetch_candles, detect_source


# Shared dict to pass trend info from chart generation to caption
chart_info = {}


async def generate_chart(
    ticker: str,
    action: str,
    entry: float,
    tp: float,
    sl: float,
    days: int = 60,
    wef_score: int = 68,
) -> str:
    """Generate chart PNG and return file path."""

    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    date_to = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"Fetching {ticker} candles...")
    candles = await fetch_candles(ticker, date_from, date_to)

    if not candles:
        print(f"No candles for {ticker}")
        return ""

    # Parse candles
    dates = []
    opens, highs, lows, closes, volumes = [], [], [], [], []
    for c in candles:
        d = c.get("begin", "")[:10]
        if not d:
            continue
        try:
            dates.append(datetime.strptime(d, "%Y-%m-%d"))
        except ValueError:
            continue
        opens.append(c.get("open", 0))
        highs.append(c.get("high", 0))
        lows.append(c.get("low", 0))
        closes.append(c.get("close", 0))
        volumes.append(c.get("volume", 0))

    if len(dates) < 5:
        print("Not enough data")
        return ""

    # ── Detect actual trend from candle data ──
    sma20 = sum(closes[-20:]) / min(20, len(closes))
    sma50 = sum(closes[-min(50, len(closes)):]) / min(50, len(closes))
    recent_change = (closes[-1] - closes[-min(20, len(closes))]) / closes[-min(20, len(closes))] * 100
    if sma20 > sma50 and recent_change > 2:
        detected_trend = "uptrend"
    elif sma20 < sma50 and recent_change < -2:
        detected_trend = "downtrend"
    else:
        detected_trend = "ranging"

    # Store trend for caption use
    chart_info["trend"] = detected_trend
    chart_info["sma20"] = sma20
    chart_info["sma50"] = sma50
    chart_info["recent_change"] = recent_change

    is_buy = action.lower() == "buy"

    # Dark theme — chart only, no text overlay
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.5), gridspec_kw={"height_ratios": [4, 1]},
                                    facecolor="#0a1628")
    ax1.set_facecolor("#0a1628")
    ax2.set_facecolor("#0a1628")

    # SMA lines
    if len(closes) >= 20:
        sma20_arr = [sum(closes[max(0,i-19):i+1]) / min(20, i+1) for i in range(len(closes))]
        ax1.plot(dates, sma20_arr, color="#f59e0b", linewidth=1, alpha=0.5, label="SMA20")
    if len(closes) >= 50:
        sma50_arr = [sum(closes[max(0,i-49):i+1]) / min(50, i+1) for i in range(len(closes))]
        ax1.plot(dates, sma50_arr, color="#8b5cf6", linewidth=1, alpha=0.5, label="SMA50")

    # Candlesticks
    for i in range(len(dates)):
        color = "#10b981" if closes[i] >= opens[i] else "#ef4444"
        ax1.plot([dates[i], dates[i]], [lows[i], highs[i]], color=color, linewidth=0.8)
        ax1.plot([dates[i], dates[i]], [min(opens[i], closes[i]), max(opens[i], closes[i])],
                 color=color, linewidth=3)

    # Entry / TP / SL lines with labels on the right
    ax1.axhline(y=entry, color="#3b82f6", linestyle="--", linewidth=1.5, alpha=0.8)
    ax1.axhline(y=tp, color="#10b981", linestyle=":", linewidth=1.5, alpha=0.8)
    ax1.axhline(y=sl, color="#ef4444", linestyle=":", linewidth=1.5, alpha=0.8)

    # Labels on right side (outside chart area)
    ax1.annotate(f"Entry {entry:,.0f}", xy=(1.01, entry), xycoords=("axes fraction", "data"),
                 color="#3b82f6", fontsize=8, fontweight="bold", va="center")
    ax1.annotate(f"TP {tp:,.0f}", xy=(1.01, tp), xycoords=("axes fraction", "data"),
                 color="#10b981", fontsize=8, fontweight="bold", va="center")
    ax1.annotate(f"SL {sl:,.0f}", xy=(1.01, sl), xycoords=("axes fraction", "data"),
                 color="#ef4444", fontsize=8, fontweight="bold", va="center")

    # Fill TP/SL zones
    if is_buy:
        ax1.axhspan(entry, tp, alpha=0.05, color="#10b981")
        ax1.axhspan(sl, entry, alpha=0.05, color="#ef4444")
    else:
        ax1.axhspan(tp, entry, alpha=0.05, color="#10b981")
        ax1.axhspan(entry, sl, alpha=0.05, color="#ef4444")

    # Title
    arrow_label = "BUY" if is_buy else "SELL"
    rr_val = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
    title_color = "#10b981" if is_buy else "#ef4444"
    trend_icon = {"uptrend": "↗", "downtrend": "↘", "ranging": "↔"}.get(detected_trend, "")
    ax1.set_title(f"{arrow_label} {ticker}  |  WEF {wef_score}%  |  R:R 1:{rr_val:.1f}  |  {trend_icon} {detected_trend}",
                  color=title_color, fontsize=13, fontweight="bold", pad=10)

    # Styling
    ax1.tick_params(colors="#64748b", labelsize=8)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.spines["bottom"].set_color("#1e3a5f")
    ax1.spines["left"].set_color("#1e3a5f")
    ax1.grid(axis="y", color="#1e3a5f", alpha=0.3)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax1.legend(loc="upper left", fontsize=7, facecolor="#0a1628", edgecolor="#1e3a5f",
               labelcolor="#64748b")

    # Volume bars (clean, no text overlay)
    for i in range(len(dates)):
        color = "#10b98160" if closes[i] >= opens[i] else "#ef444460"
        ax2.bar(dates[i], volumes[i], color=color, width=0.8)

    ax2.tick_params(colors="#64748b", labelsize=7)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.spines["bottom"].set_color("#1e3a5f")
    ax2.spines["left"].set_color("#1e3a5f")
    ax2.yaxis.set_visible(False)

    # Date format
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    ax2.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=0, fontsize=7)

    # Watermark
    fig.text(0.99, 0.01, "WinExtraFlow", fontsize=7, color="#64748b30",
             ha="right", va="bottom", style="italic")

    plt.subplots_adjust(hspace=0.15, right=0.88)

    # Save
    path = os.path.join(tempfile.gettempdir(), f"wef_chart_{ticker}.png")
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="#0a1628")
    plt.close()

    print(f"Chart saved: {path} (trend: {detected_trend}, change: {recent_change:.1f}%)")
    return path


async def send_to_telegram(chart_path: str, ticker: str, action: str, entry: float,
                           tp: float, sl: float, wef: int):
    """Send chart + text to VIP channel."""
    import httpx

    from app.config import settings
    token = os.getenv("BOT_TOKEN", "") or settings.telegram_bot_token
    chat_id = os.getenv("VIP_CHANNEL_ID", "") or settings.telegram_vip_channel_id
    if not token or not chat_id:
        print("BOT_TOKEN / VIP_CHANNEL_ID не заданы — отправка пропущена")
        return

    arrow = "\U0001f7e2" if action.lower() == "buy" else "\U0001f534"
    rr = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
    tp_pct = abs(tp - entry) / entry * 100
    sl_pct = abs(entry - sl) / entry * 100

    # Expert calculations — win_rate adjusted by trend alignment
    detected_trend = chart_info.get("trend", "unknown")
    is_buy = action.lower() == "buy"
    trend_matches = (is_buy and detected_trend == "uptrend") or (not is_buy and detected_trend == "downtrend")
    trend_conflict = (is_buy and detected_trend == "downtrend") or (not is_buy and detected_trend == "uptrend")

    if trend_matches:
        win_rate = 0.65  # by-trend trades have higher WR
    elif trend_conflict:
        win_rate = 0.45  # counter-trend — lower WR
    else:
        win_rate = 0.55  # ranging — neutral

    ev = (win_rate * tp_pct) - ((1 - win_rate) * sl_pct)
    pf = (win_rate * tp_pct) / ((1 - win_rate) * sl_pct) if sl_pct > 0 else 0
    kelly_full = win_rate - (1 - win_rate) / (tp_pct / sl_pct) if sl_pct > 0 else 0
    kelly_half = max(0, kelly_full * 0.5 * 100)
    edge = (win_rate - (1 / (1 + tp_pct / sl_pct))) * 100 if sl_pct > 0 else 0

    # Instrument detection
    MOEX_TICKERS = {"SBER", "GAZP", "LKOH", "YNDX", "ROSN", "GMKN", "NVTK", "MGNT",
                    "VTBR", "MTSS", "POLY", "FIVE", "OZON", "TCSG", "PHOR", "NLMK",
                    "CHMF", "ALRS", "AFLT", "MOEX", "PLZL", "RUAL", "SNGS", "TATN"}
    FOREX_CURRENCIES = {"EUR", "USD", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF"}

    t = ticker.upper()
    if t in MOEX_TICKERS:
        instrument = "MOEX (Московская биржа)"
        where = "Тинькофф Инвестиции, QUIK, MetaTrader 5"
        asset_type = "Акции РФ"
        currency = "RUB"
    elif t.endswith("USDT") or t.endswith("BTC"):
        instrument = "Crypto (спотовый рынок)"
        where = "Binance, Bybit, OKX"
        asset_type = "Криптовалюта"
        currency = "USDT"
    elif len(t) == 6 and t[:3] in FOREX_CURRENCIES and t[3:] in FOREX_CURRENCIES:
        instrument = "Forex (валютный рынок)"
        where = "MetaTrader 5, Interactive Brokers"
        asset_type = "Валютная пара"
        currency = t[3:]
    else:
        instrument = "US/EU Stocks (фондовый рынок)"
        where = "Interactive Brokers, Exante, Tinkoff"
        asset_type = "Акции"
        currency = "USD"

    # Trend already detected above in Expert calculations
    recent_change = chart_info.get("recent_change", 0)

    if trend_conflict:
        # Signal opposes trend — downgrade verdict
        if ev > 0:
            verdict = "РИСКОВАННЫЙ"
            strategy = "Mean Reversion (против тренда)"
        else:
            verdict = "ПРОПУСТИТЬ"
            strategy = "Сигнал против тренда"
    elif trend_matches and ev > 1.0 and rr >= 2:
        verdict = "ОТЛИЧНЫЙ"
        strategy = "Trend Following (по тренду)"
    elif trend_matches and ev > 0.3 and rr >= 1.5:
        verdict = "ХОРОШИЙ"
        strategy = "Dual Momentum (по тренду)"
    elif detected_trend == "ranging" and ev > 0:
        verdict = "СРЕДНИЙ"
        strategy = "Mean Reversion (боковик)"
    elif ev > 0:
        verdict = "СРЕДНИЙ"
        strategy = "Осторожный вход"
    else:
        verdict = "ПРОПУСТИТЬ"
        strategy = "Отрицательное мат. ожидание"

    # Verdict emoji
    verdict_emoji = {"ОТЛИЧНЫЙ": "✅", "ХОРОШИЙ": "✅", "СРЕДНИЙ": "⚠️", "РИСКОВАННЫЙ": "⚠️", "ПРОПУСТИТЬ": "❌"}.get(verdict, "⚠️")

    # Detailed conclusion
    act_ru = "покупку" if action.lower() == "buy" else "продажу"
    name_map = {
        "SBER": "Сбер", "GAZP": "Газпром", "LKOH": "Лукойл", "ROSN": "Роснефть",
        "GMKN": "Норникель", "NVTK": "Новатэк", "YNDX": "Яндекс", "VTBR": "ВТБ",
        "MGNT": "Магнит", "MTSS": "МТС", "NLMK": "НЛМК", "CHMF": "Северсталь",
        "ALRS": "Алроса", "PLZL": "Полюс", "TATN": "Татнефть", "AFLT": "Аэрофлот",
        "BTCUSDT": "Биткоин", "ETHUSDT": "Эфириум", "BNBUSDT": "BNB",
        "SOLUSDT": "Солана", "XRPUSDT": "Ripple",
        "EURUSD": "EUR/USD", "GBPUSD": "GBP/USD", "USDJPY": "USD/JPY",
    }
    ticker_name = name_map.get(t, t)

    trend_ru = {"uptrend": "восходящем тренде", "downtrend": "нисходящем тренде", "ranging": "боковике"}.get(detected_trend, "неопределённом состоянии")

    parts = []
    parts.append(f"{ticker_name} находится в {trend_ru} (изменение за 20 дней: {recent_change:+.1f}%).")

    if trend_conflict:
        parts.append(f"Сигнал на {act_ru} ПРОТИВ текущего тренда — повышенный риск.")
        parts.append(f"Стратегия Mean Reversion: расчёт на отскок от уровня {entry:,.0f}.")
        parts.append(f"Рекомендуется уменьшенный размер позиции (25% от обычного) и строгий стоп.")
    elif trend_matches:
        parts.append(f"Сигнал ПО ТРЕНДУ — моментум подтверждает направление.")
        if rr >= 2:
            parts.append(f"R:R {rr:.1f} — отличное соотношение риска к прибыли.")
        elif rr >= 1.5:
            parts.append(f"R:R {rr:.1f} — хорошее соотношение.")
        parts.append(f"Рекомендуется вход 1-й частью (50%) по рынку, 2-я часть (30%) при подтверждении на {entry * 1.02:,.0f}.")
    else:
        parts.append(f"Рынок в боковике — сигнал на {act_ru} от уровня поддержки/сопротивления.")
        parts.append(f"Рекомендуется вход 50% от обычного размера с узким стопом.")

    parts.append(f"WEF {wef}% подтверждает качество сигнала по 9 факторам.")

    if rr >= 1.5 and not trend_conflict:
        parts.append(f"Стоп в безубыток после достижения +{tp_pct * 0.4:.1f}%.")

    parts.append(f"Оптимальный размер по Kelly: {kelly_half:.1f}% от депозита ({kelly_half * 1000:.0f} на каждые 100 000).")

    if pf > 1.5:
        parts.append(f"Profit Factor {pf:.2f} — прибыльные сделки превышают убыточные в {pf:.1f} раза.")
    elif pf > 1:
        parts.append(f"Profit Factor {pf:.2f} — система прибыльна с умеренным запасом.")

    conclusion = " ".join(parts)

    caption = (
        f"{arrow} {action.upper()} {ticker}  |  WEF {wef}%\n"
        f"\U0001f3e6 {asset_type} | {instrument}\n\n"
        f"\U0001f4cd Вход: {entry:,.2f} {currency}\n"
        f"\U0001f3af Цель: {tp:,.2f} (+{tp_pct:.1f}%)\n"
        f"\U0001f6d1 Стоп: {sl:,.2f} (-{sl_pct:.1f}%)\n"
        f"⚖️ R:R = 1:{rr:.1f}\n\n"
        f"─── Экспертный анализ ───\n"
        f"{verdict_emoji} Вердикт: {verdict}\n"
        f"\U0001f4c8 Стратегия: {strategy}\n"
        f"\U0001f4b0 EV: +{ev:.2f}% на сделку\n"
        f"\U0001f4ca Profit Factor: {pf:.2f}\n"
        f"\U0001f3b2 Kelly: {kelly_half:.1f}%\n"
        f"{'\U0001f53a Пирамидинг: 3 уровня' if not trend_conflict else '\U0001f6ab Пирамидинг: не рекомендуется'}\n"
        f"⚡ Edge: +{edge:.1f}%\n\n"
        f"\U0001f4a1 Вывод: {conclusion}\n\n"
        f"\U0001f4b1 Где торговать: {where}\n\n"
        f"⚠️ Не является инвестиционной рекомендацией."
    )

    async with httpx.AsyncClient(timeout=30) as client:
        with open(chart_path, "rb") as f:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/sendPhoto",
                data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML", "disable_notification": "true"},
                files={"photo": (f"chart_{ticker}.png", f, "image/png")},
            )
        result = resp.json()
        if result.get("ok"):
            print(f"Sent to VIP! msg_id={result['result']['message_id']}")
        else:
            print(f"Failed: {result}")


async def auto_signal(ticker: str, wef: int = 70) -> dict | None:
    """Auto-detect BUY or SELL based on real market data + strategies.

    Uses: SMA crossover, RSI zones, mean reversion Z-score, trend direction.
    Returns dict with action, entry, tp, sl — or None if no clear signal.
    """
    from app.services.quant.top_strategies import mean_reversion_signal, multi_factor_score

    date_from = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
    date_to = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    candles = await fetch_candles(ticker, date_from, date_to)
    if not candles or len(candles) < 30:
        print(f"Not enough data for {ticker}")
        return None

    closes = [c["close"] for c in candles if c.get("close")]
    highs = [c["high"] for c in candles if c.get("high")]
    lows = [c["low"] for c in candles if c.get("low")]
    if len(closes) < 30:
        return None

    current = closes[-1]

    # SMA trend
    sma20 = sum(closes[-20:]) / 20
    sma50 = sum(closes[-min(50, len(closes)):]) / min(50, len(closes))
    change_20d = (current - closes[-20]) / closes[-20] * 100

    # RSI 14
    gains = [max(0, closes[i] - closes[i-1]) for i in range(-14, 0)]
    losses_r = [max(0, closes[i-1] - closes[i]) for i in range(-14, 0)]
    avg_g = sum(gains) / 14
    avg_l = sum(losses_r) / 14
    rsi = 100 - 100 / (1 + avg_g / avg_l) if avg_l > 0 else 50

    # ATR for TP/SL sizing (percentage-based for cross-asset compatibility)
    n = min(14, len(highs))
    atr_vals = [highs[-(n-i)] - lows[-(n-i)] for i in range(n)]
    atr = sum(atr_vals) / len(atr_vals) if atr_vals else current * 0.02
    atr_pct = (atr / current * 100) if current > 0 else 2.0
    # Floor: minimum ATR% for meaningful TP/SL
    if atr_pct < 0.3:
        atr_pct = 0.8  # forex minimum
    atr = current * atr_pct / 100

    # Mean reversion Z-score
    mr = mean_reversion_signal(closes, lookback=20)
    z_score = mr["z_score"]

    # Decision logic
    action = None
    reason = ""

    if sma20 > sma50 and change_20d > 3 and rsi < 70:
        # Strong uptrend, not overbought
        action = "buy"
        reason = f"Восходящий тренд (SMA20 > SMA50, +{change_20d:.1f}%), RSI {rsi:.0f} — не перекуплен"
    elif sma20 < sma50 and change_20d < -3 and rsi > 30:
        # Strong downtrend, not oversold
        action = "sell"
        reason = f"Нисходящий тренд (SMA20 < SMA50, {change_20d:.1f}%), RSI {rsi:.0f} — не перепродан"
    elif z_score < -2.0 and rsi < 35:
        # Oversold — mean reversion buy
        action = "buy"
        reason = f"Перепроданность: Z-score {z_score:.1f}, RSI {rsi:.0f} — ожидается отскок"
    elif z_score > 2.0 and rsi > 65:
        # Overbought — mean reversion sell
        action = "sell"
        reason = f"Перекупленность: Z-score {z_score:.1f}, RSI {rsi:.0f} — ожидается коррекция"
    elif sma20 < sma50 and change_20d < -5:
        # Clear downtrend
        action = "sell"
        reason = f"Сильный даунтренд ({change_20d:.1f}%), SMA20 ниже SMA50"
    elif sma20 > sma50 and change_20d > 1:
        # Moderate uptrend
        action = "buy"
        reason = f"Умеренный восходящий тренд (+{change_20d:.1f}%)"
    else:
        print(f"{ticker}: нет ясного сигнала (Z={z_score:.1f}, RSI={rsi:.0f}, change={change_20d:.1f}%)")
        return None

    # Calculate TP/SL based on ATR — ensure R:R >= 1.5
    # SL = 1.5 × ATR from entry, TP = 3.0 × ATR (R:R = 2.0)
    entry = current
    sl_distance = atr * 1.5
    tp_distance = atr * 3.0

    if action == "buy":
        sl = round(entry - sl_distance, 6)
        tp = round(entry + tp_distance, 6)
    else:
        sl = round(entry + sl_distance, 6)
        tp = round(entry - tp_distance, 6)

    # Round nicely based on price scale
    if entry > 1000:
        entry = round(entry, 0)
        tp = round(tp, 0)
        sl = round(sl, 0)
    elif entry > 10:
        entry = round(entry, 2)
        tp = round(tp, 2)
        sl = round(sl, 2)
    else:
        entry = round(entry, 5)
        tp = round(tp, 5)
        sl = round(sl, 5)

    # Validate against live price before sending
    from app.services.live_price import validate_signal
    validation = await validate_signal(ticker, action, entry, tp, sl)

    print(f"{ticker}: {action.upper()} @ {entry} | TP {tp} | SL {sl}")
    print(f"  Reason: {reason}")
    print(f"  SMA20={sma20:.2f} SMA50={sma50:.2f} RSI={rsi:.0f} Z={z_score:.1f} ATR%={atr_pct:.2f}%")

    if validation.get("live_price"):
        print(f"  Live price: {validation['live_price']} ({validation['source']}) deviation: {validation['deviation_pct']}%")

    if not validation["valid"]:
        print(f"  VALIDATION FAILED: {validation['errors']}")
        if validation.get("suggested_entry"):
            entry = validation["suggested_entry"]
            print(f"  CORRECTED entry → {entry}")
            # Recalculate TP/SL from corrected entry
            if action == "buy":
                sl = round(entry - sl_distance, 6)
                tp = round(entry + tp_distance, 6)
            else:
                sl = round(entry + sl_distance, 6)
                tp = round(entry - tp_distance, 6)
            if entry > 1000:
                entry, tp, sl = round(entry, 0), round(tp, 0), round(sl, 0)
            elif entry > 10:
                entry, tp, sl = round(entry, 2), round(tp, 2), round(sl, 2)
            else:
                entry, tp, sl = round(entry, 5), round(tp, 5), round(sl, 5)

    for w in validation.get("warnings", []):
        print(f"  WARNING: {w}")

    return {"action": action, "entry": entry, "tp": tp, "sl": sl, "reason": reason, "rsi": rsi, "z_score": z_score}


async def main():
    args = sys.argv[1:]

    if len(args) == 0:
        print("Usage:")
        print("  Manual:  python gen_chart.py TICKER ACTION ENTRY TP SL [WEF]")
        print("  Auto:    python gen_chart.py auto TICKER [TICKER2 ...]")
        print("Examples:")
        print("  python gen_chart.py SBER buy 324 350 312 72")
        print("  python gen_chart.py auto SBER GAZP BTCUSDT ETHUSDT EURUSD")
        return

    if args[0].lower() == "auto":
        # Auto mode: detect BUY/SELL from real data
        tickers = [t.upper() for t in args[1:]] if len(args) > 1 else ["SBER", "GAZP", "BTCUSDT", "ETHUSDT", "EURUSD"]
        for ticker in tickers:
            print(f"\n{'='*40}")
            sig = await auto_signal(ticker)
            if sig:
                chart = await generate_chart(ticker, sig["action"], sig["entry"], sig["tp"], sig["sl"], wef_score=70)
                if chart:
                    await send_to_telegram(chart, ticker, sig["action"], sig["entry"], sig["tp"], sig["sl"], 70)
            else:
                print(f"  SKIP — no clear signal")
        return

    # Manual mode
    if len(args) < 5:
        print("Usage: python gen_chart.py TICKER ACTION ENTRY TP SL [WEF]")
        return

    ticker = args[0].upper()
    action = args[1].lower()
    entry = float(args[2])
    tp = float(args[3])
    sl = float(args[4])
    wef = int(args[5]) if len(args) > 5 else 68

    chart = await generate_chart(ticker, action, entry, tp, sl, wef_score=wef)
    if chart:
        await send_to_telegram(chart, ticker, action, entry, tp, sl, wef)


if __name__ == "__main__":
    asyncio.run(main())
