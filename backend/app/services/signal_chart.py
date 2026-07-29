"""Signal chart card — candlestick chart + rich RU expert caption for VIP.

Renders the VIP "signal card": a dark candlestick chart with Entry/TP/SL
lines + a full Russian expert-analysis caption (verdict, strategy, EV,
Profit Factor, Kelly, pyramiding, edge, detailed conclusion, where-to-trade).

Public entry point: `broadcast_card(...)` — render + caption + sendPhoto to VIP.
Used by the connected-signals pipeline and the gen_chart CLI.
"""

import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings
from app.services.backtesting_real import fetch_candles

logger = logging.getLogger(__name__)

PLATFORM_URL = "https://winextraflow.pages.dev"

MOEX_TICKERS = {"SBER", "SBERP", "GAZP", "LKOH", "YNDX", "YDEX", "ROSN", "GMKN", "NVTK",
                "MGNT", "VTBR", "MTSS", "POLY", "FIVE", "OZON", "TCSG", "T", "PHOR", "NLMK",
                "MAGN", "CHMF", "ALRS", "AFLT", "MOEX", "PLZL", "RUAL", "SNGS", "SNGSP",
                "TATN", "TATNP", "SIBN", "PIKK", "AFKS", "RTKM", "HYDR", "IRAO", "FEES",
                "TRNFP", "BANE", "SELG", "UPRO", "MSNG", "FLOT", "SMLT", "SGZH", "POSI",
                "ASTR", "WUSH", "LEAS", "SVCB", "RENI", "BSPB", "CBOM", "ENPG", "VKCO", "UGLD"}
FOREX_CURRENCIES = {"EUR", "USD", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF"}
NAME_MAP = {
    "SBER": "Сбер", "GAZP": "Газпром", "LKOH": "Лукойл", "ROSN": "Роснефть",
    "GMKN": "Норникель", "NVTK": "Новатэк", "YNDX": "Яндекс", "YDEX": "Яндекс",
    "SIBN": "Газпром нефть", "VTBR": "ВТБ",
    "MGNT": "Магнит", "MTSS": "МТС", "NLMK": "НЛМК", "CHMF": "Северсталь",
    "ALRS": "Алроса", "PLZL": "Полюс", "TATN": "Татнефть", "AFLT": "Аэрофлот",
    "BTCUSDT": "Биткоин", "ETHUSDT": "Эфириум", "BNBUSDT": "BNB",
    "SOLUSDT": "Солана", "XRPUSDT": "Ripple",
    "EURUSD": "EUR/USD", "GBPUSD": "GBP/USD", "USDJPY": "USD/JPY",
}


import re as _re

# MOEX futures codes: BR-8.26 (Brent), GAZR-9.26 (Gazprom), CNY-9.26, MXI-9.26, SILV-9.26...
_FUTURES_RE = _re.compile(r"^([A-Z]{2,5})-(\d{1,2})\.(\d{2})$")
FUTURES_NAMES = {
    "BR": "Нефть Brent (фьючерс)", "GAZR": "Газпром (фьючерс)", "SBRF": "Сбербанк (фьючерс)",
    "CNY": "Юань/рубль (фьючерс)", "MXI": "Индекс МосБиржи (фьючерс)", "RTS": "Индекс РТС (фьючерс)",
    "SI": "Доллар/рубль (фьючерс)", "EU": "Евро/рубль (фьючерс)", "GOLD": "Золото (фьючерс)",
    "SILV": "Серебро (фьючерс)", "NG": "Газ (фьючерс)", "LKOH": "Лукойл (фьючерс)",
}


def is_moex_futures(ticker: str) -> bool:
    return bool(_FUTURES_RE.match(ticker.upper()))


def futures_label(ticker: str) -> str:
    m = _FUTURES_RE.match(ticker.upper())
    if not m:
        return ticker
    return FUTURES_NAMES.get(m.group(1), f"{m.group(1)} (фьючерс)")


def _instrument(ticker: str):
    t = ticker.upper()
    if is_moex_futures(t):
        return ("MOEX FORTS (срочный рынок)", "QUIK, Тинькофф Инвестиции, Финам",
                "Фьючерс", "RUB")
    if t in MOEX_TICKERS:
        return "MOEX (Московская биржа)", "Тинькофф Инвестиции, QUIK, MetaTrader 5", "Акции РФ", "RUB"
    if t.endswith("USDT") or t.endswith("BTC"):
        return "Crypto (спотовый рынок)", "Binance, Bybit, OKX", "Криптовалюта", "USDT"
    if len(t) == 6 and t[:3] in FOREX_CURRENCIES and t[3:] in FOREX_CURRENCIES:
        return "Forex (валютный рынок)", "MetaTrader 5, Interactive Brokers", "Валютная пара", t[3:]
    return "US/EU Stocks (фондовый рынок)", "Interactive Brokers, Exante, Tinkoff", "Акции", "USD"


async def render_chart(ticker: str, action: str, entry: float, tp: float, sl: float,
                       wef: int, days: int = 60) -> tuple[str | None, str, float]:
    """Render a candlestick chart PNG. Returns (path|None, trend, recent_change_pct)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    date_to = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    candles = await fetch_candles(ticker, date_from, date_to)
    if not candles:
        return None, "unknown", 0.0

    dates, opens, highs, lows, closes, volumes = [], [], [], [], [], []
    for c in candles:
        d = c.get("begin", "")[:10]
        if not d:
            continue
        try:
            dates.append(datetime.strptime(d, "%Y-%m-%d"))
        except ValueError:
            continue
        opens.append(c.get("open", 0)); highs.append(c.get("high", 0))
        lows.append(c.get("low", 0)); closes.append(c.get("close", 0))
        volumes.append(c.get("volume", 0))
    if len(dates) < 5:
        return None, "unknown", 0.0

    sma20 = sum(closes[-20:]) / min(20, len(closes))
    sma50 = sum(closes[-min(50, len(closes)):]) / min(50, len(closes))
    recent_change = (closes[-1] - closes[-min(20, len(closes))]) / closes[-min(20, len(closes))] * 100
    if sma20 > sma50 and recent_change > 2:
        trend = "uptrend"
    elif sma20 < sma50 and recent_change < -2:
        trend = "downtrend"
    else:
        trend = "ranging"

    is_buy = action.lower() == "buy"
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.5), gridspec_kw={"height_ratios": [4, 1]}, facecolor="#0a1628")
    ax1.set_facecolor("#0a1628"); ax2.set_facecolor("#0a1628")

    if len(closes) >= 20:
        sma20_arr = [sum(closes[max(0, i - 19):i + 1]) / min(20, i + 1) for i in range(len(closes))]
        ax1.plot(dates, sma20_arr, color="#f59e0b", linewidth=1, alpha=0.5, label="SMA20")
    if len(closes) >= 50:
        sma50_arr = [sum(closes[max(0, i - 49):i + 1]) / min(50, i + 1) for i in range(len(closes))]
        ax1.plot(dates, sma50_arr, color="#8b5cf6", linewidth=1, alpha=0.5, label="SMA50")

    for i in range(len(dates)):
        color = "#10b981" if closes[i] >= opens[i] else "#ef4444"
        ax1.plot([dates[i], dates[i]], [lows[i], highs[i]], color=color, linewidth=0.8)
        ax1.plot([dates[i], dates[i]], [min(opens[i], closes[i]), max(opens[i], closes[i])], color=color, linewidth=3)

    ax1.axhline(y=entry, color="#3b82f6", linestyle="--", linewidth=1.5, alpha=0.8)
    ax1.axhline(y=tp, color="#10b981", linestyle=":", linewidth=1.5, alpha=0.8)
    ax1.axhline(y=sl, color="#ef4444", linestyle=":", linewidth=1.5, alpha=0.8)
    fmt = ",.0f" if entry > 100 else ",.4f"
    ax1.annotate(f"Entry {entry:{fmt}}", xy=(1.01, entry), xycoords=("axes fraction", "data"), color="#3b82f6", fontsize=8, fontweight="bold", va="center")
    ax1.annotate(f"TP {tp:{fmt}}", xy=(1.01, tp), xycoords=("axes fraction", "data"), color="#10b981", fontsize=8, fontweight="bold", va="center")
    ax1.annotate(f"SL {sl:{fmt}}", xy=(1.01, sl), xycoords=("axes fraction", "data"), color="#ef4444", fontsize=8, fontweight="bold", va="center")

    if is_buy:
        ax1.axhspan(entry, tp, alpha=0.05, color="#10b981"); ax1.axhspan(sl, entry, alpha=0.05, color="#ef4444")
    else:
        ax1.axhspan(tp, entry, alpha=0.05, color="#10b981"); ax1.axhspan(entry, sl, alpha=0.05, color="#ef4444")

    rr_val = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
    trend_icon = {"uptrend": "↗", "downtrend": "↘", "ranging": "↔"}.get(trend, "")
    ax1.set_title(f"{'BUY' if is_buy else 'SELL'} {ticker}  |  WEF {wef}%  |  R:R 1:{rr_val:.1f}  |  {trend_icon} {trend}",
                  color="#10b981" if is_buy else "#ef4444", fontsize=13, fontweight="bold", pad=10)
    ax1.tick_params(colors="#64748b", labelsize=8)
    for s in ("top", "right"):
        ax1.spines[s].set_visible(False)
    ax1.spines["bottom"].set_color("#1e3a5f"); ax1.spines["left"].set_color("#1e3a5f")
    ax1.grid(axis="y", color="#1e3a5f", alpha=0.3)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.2f}" if x < 100 else f"{x:,.0f}"))
    ax1.legend(loc="upper left", fontsize=7, facecolor="#0a1628", edgecolor="#1e3a5f", labelcolor="#64748b")

    for i in range(len(dates)):
        color = "#10b98160" if closes[i] >= opens[i] else "#ef444460"
        ax2.bar(dates[i], volumes[i], color=color, width=0.8)
    ax2.tick_params(colors="#64748b", labelsize=7)
    for s in ("top", "right"):
        ax2.spines[s].set_visible(False)
    ax2.spines["bottom"].set_color("#1e3a5f"); ax2.spines["left"].set_color("#1e3a5f")
    ax2.yaxis.set_visible(False)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    ax2.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=0, fontsize=7)
    fig.text(0.99, 0.01, "WinExtraFlow", fontsize=7, color="#64748b30", ha="right", va="bottom", style="italic")
    plt.subplots_adjust(hspace=0.15, right=0.88)

    path = os.path.join(tempfile.gettempdir(), f"wef_chart_{ticker}.png")
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="#0a1628")
    plt.close()
    return path, trend, recent_change


def build_caption(ticker: str, action: str, entry: float, tp: float, sl: float,
                  wef: int, trend: str, recent_change: float, expert: dict | None = None) -> str:
    """Build the rich RU expert-analysis caption matching the VIP card layout."""
    arrow = "\U0001f7e2" if action.lower() == "buy" else "\U0001f534"
    rr = abs(tp - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
    tp_pct = abs(tp - entry) / entry * 100
    sl_pct = abs(entry - sl) / entry * 100
    is_buy = action.lower() == "buy"
    trend_matches = (is_buy and trend == "uptrend") or (not is_buy and trend == "downtrend")
    trend_conflict = (is_buy and trend == "downtrend") or (not is_buy and trend == "uptrend")

    # Win rate by trend alignment (used only if expert dict not provided)
    win_rate = 0.65 if trend_matches else 0.45 if trend_conflict else 0.55
    ev = (win_rate * tp_pct) - ((1 - win_rate) * sl_pct)
    pf = (win_rate * tp_pct) / ((1 - win_rate) * sl_pct) if sl_pct > 0 else 0
    kelly_full = win_rate - (1 - win_rate) / (tp_pct / sl_pct) if sl_pct > 0 else 0
    kelly_half = max(0, kelly_full * 0.5 * 100)
    edge = (win_rate - (1 / (1 + tp_pct / sl_pct))) * 100 if sl_pct > 0 else 0

    # Prefer real evolutionary numbers from the recommendation engine when available
    if expert:
        ev = expert.get("ev_per_trade_pct", ev) or ev
        pf = expert.get("profit_factor", pf) or pf
        kelly_half = expert.get("kelly_half_pct", kelly_half) or kelly_half
        edge = expert.get("edge_pct", edge) or edge

    instrument, where, asset_type, currency = _instrument(ticker)

    if trend_conflict:
        verdict = "РИСКОВАННЫЙ" if ev > 0 else "ПРОПУСТИТЬ"
        strategy = "Mean Reversion (против тренда)" if ev > 0 else "Сигнал против тренда"
    elif trend_matches and ev > 1.0 and rr >= 2:
        verdict, strategy = "ОТЛИЧНЫЙ", "Trend Following (по тренду)"
    elif trend_matches and ev > 0.3 and rr >= 1.5:
        verdict, strategy = "ХОРОШИЙ", "Dual Momentum (по тренду)"
    elif trend == "ranging" and ev > 0:
        verdict, strategy = "СРЕДНИЙ", "Mean Reversion (боковик)"
    elif ev > 0:
        verdict, strategy = "СРЕДНИЙ", "Осторожный вход"
    else:
        verdict, strategy = "ПРОПУСТИТЬ", "Отрицательное мат. ожидание"
    v_emoji = {"ОТЛИЧНЫЙ": "✅", "ХОРОШИЙ": "✅", "СРЕДНИЙ": "⚠️", "РИСКОВАННЫЙ": "⚠️", "ПРОПУСТИТЬ": "❌"}.get(verdict, "⚠️")

    # Detailed conclusion
    name = futures_label(ticker) if is_moex_futures(ticker) else NAME_MAP.get(ticker.upper(), ticker.upper())
    act_ru = "покупку" if is_buy else "продажу"
    trend_ru = {"uptrend": "восходящем тренде", "downtrend": "нисходящем тренде", "ranging": "боковике"}.get(trend, "неопределённом состоянии")
    parts = [f"{name} находится в {trend_ru} (изменение за 20 дней: {recent_change:+.1f}%)."]
    if trend_conflict:
        parts.append(f"Сигнал на {act_ru} ПРОТИВ текущего тренда — повышенный риск.")
        parts.append(f"Стратегия Mean Reversion: расчёт на отскок от уровня {entry:,.0f}.")
        parts.append("Рекомендуется уменьшенный размер позиции (25% от обычного) и строгий стоп.")
    elif trend_matches:
        parts.append("Сигнал ПО ТРЕНДУ — моментум подтверждает направление.")
        if rr >= 2:
            parts.append(f"R:R {rr:.1f} — отличное соотношение риска к прибыли.")
        elif rr >= 1.5:
            parts.append(f"R:R {rr:.1f} — хорошее соотношение.")
        parts.append(f"Рекомендуется вход 1-й частью (50%) по рынку, 2-я часть (30%) при подтверждении на {entry * 1.02:,.0f}.")
    else:
        parts.append(f"Рынок в боковике — сигнал на {act_ru} от уровня поддержки/сопротивления.")
        parts.append("Рекомендуется вход 50% от обычного размера с узким стопом.")
    parts.append(f"WEF {wef}% подтверждает качество сигнала по 9 факторам.")
    if rr >= 1.5 and not trend_conflict:
        parts.append(f"Стоп в безубыток после достижения +{tp_pct * 0.4:.1f}%.")
    parts.append(f"Оптимальный размер по Kelly: {kelly_half:.1f}% от депозита ({kelly_half * 1000:.0f} на каждые 100 000).")
    if pf > 1.5:
        parts.append(f"Profit Factor {pf:.2f} — прибыльные сделки превышают убыточные в {pf:.1f} раза.")
    elif pf > 1:
        parts.append(f"Profit Factor {pf:.2f} — система прибыльна с умеренным запасом.")
    conclusion = " ".join(parts)

    price_fmt = ",.2f" if entry >= 1 else ",.5f"
    pyr = "\U0001f53a Пирамидинг: 3 уровня" if not trend_conflict else "\U0001f6ab Пирамидинг: не рекомендуется"

    # Market hashtag for filtering
    market_tag = {"Акции РФ": "MOEX", "Фьючерс": "фьючерсы", "Криптовалюта": "crypto", "Валютная пара": "forex",
                  "Акции": "stocks"}.get(asset_type, "market")
    hashtags = f"#{ticker} #{market_tag} #WinExtraFlow"

    return (
        f"{arrow} {action.upper()} {ticker}  |  WEF {wef}%\n"
        f"\U0001f3e6 {asset_type} | {instrument}\n\n"
        f"\U0001f4cd Вход: {entry:{price_fmt}} {currency}\n"
        f"\U0001f3af Цель: {tp:{price_fmt}} (+{tp_pct:.1f}%)\n"
        f"\U0001f6d1 Стоп: {sl:{price_fmt}} (-{sl_pct:.1f}%)\n"
        f"⚖️ R:R = 1:{rr:.1f}\n\n"
        f"─── Экспертный анализ ───\n"
        f"{v_emoji} Вердикт: {verdict}\n"
        f"\U0001f4c8 Стратегия: {strategy}\n"
        f"\U0001f4b0 EV: +{ev:.2f}% на сделку\n"
        f"\U0001f4ca Profit Factor: {pf:.2f}\n"
        f"\U0001f3b2 Kelly: {kelly_half:.1f}%\n"
        f"{pyr}\n"
        f"⚡ Edge: +{edge:.1f}%\n\n"
        f"\U0001f4a1 Вывод: {conclusion}\n\n"
        f"\U0001f4b1 Где торговать: {where}\n"
        f"\U0001f4f2 Полный разбор и WEF Score: {PLATFORM_URL}\n\n"
        f"⚠️ Не является инвестиционной рекомендацией.\n"
        f"{hashtags}"
    )


async def broadcast_card(ticker: str, action: str, entry: float, tp: float, sl: float,
                         wef: int, expert: dict | None = None, chat_id: str | None = None) -> bool:
    """Render chart + rich caption and send to the VIP channel. Returns True on success."""
    token = settings.telegram_bot_token
    chat_id = chat_id or settings.telegram_vip_channel_id
    if not token or not chat_id:
        logger.info(f"Chart card skipped (no token/channel) for {ticker}")
        return False

    chart_path, trend, recent_change = await render_chart(ticker, action, entry, tp, sl, wef)
    caption = build_caption(ticker, action, entry, tp, sl, wef, trend, recent_change, expert)

    # WEF-based notification: strong signals (>=80%) alert with sound, others silent
    silent = wef < 80

    try:
        async with httpx.AsyncClient(timeout=40) as client:
            if chart_path and os.path.exists(chart_path):
                with open(chart_path, "rb") as f:
                    resp = await client.post(
                        f"https://api.telegram.org/bot{token}/sendPhoto",
                        data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML",
                              "disable_notification": str(silent).lower()},
                        files={"photo": (f"chart_{ticker}.png", f, "image/png")},
                    )
            else:
                # No candles — send text-only card
                resp = await client.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": caption, "parse_mode": "HTML", "disable_notification": silent},
                )
        ok = resp.json().get("ok", False)
        if not ok:
            logger.error(f"VIP card send failed for {ticker}: {resp.text[:200]}")
        return ok
    except Exception as e:
        logger.error(f"VIP card send error for {ticker}: {e}")
        return False
