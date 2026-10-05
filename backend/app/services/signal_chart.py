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

# Telegram allows 4096 characters in a message but only 1024 in a photo or video
# caption, and this card is always sent as one. The difference is not academic:
# the card measured 954-989 characters without the geometry baseline and
# 1123-1158 with it, so every card carrying that block was rejected with
# MEDIA_CAPTION_TOO_LONG and silently never published.
CAPTION_LIMIT = 1024

# *.pages.dev does not resolve into a usable connection from Russian networks:
# measured direct = connection closed after 15s, via proxy = 200 in 0.5s, while
# cloudflare.com itself answers fine. So the host is reachable and the block is
# specific to that hostname.
#
# Until the frontend moves to the RU VPS (deploy/nginx.conf, block "Frontend on the
# same host"), a reader in Russia clicks a dead link. This line states that as a
# fact about availability rather than as advice to install anything: since March
# 2024, Russian law penalises *promoting* means of circumventing blocks
# (ст. 13.41 КоАП), and a channel post is a public promotion.
#
# Deliberately says nothing about VPNs or any other way around the block. Russian
# law (ст. 13.41 КоАП, in force since March 2024) penalises *promoting* means of
# circumventing restrictions, and a channel post is a public promotion — so this
# states the fact and offers a lawful alternative instead: the full text published
# in the channel itself (see scripts/lesson_post.py --full).
#
# Delete this constant once the site is served from the Russian host — it stops
# being true and starts being noise.
PLATFORM_ACCESS_NOTE = (
    "🌐 Переносим сайт на российский хостинг. Если ссылка пока не открывается — "
    "полный текст публикуем здесь же, в канале."
)

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
                  wef: int, trend: str, recent_change: float, expert: dict | None = None,
                  geometry: dict | None = None) -> str:
    """Build the rich RU expert-analysis caption matching the VIP card layout.

    `geometry` is the random-entry baseline from services/signal_geometry.py: at this
    instrument's volatility, how often the target was reached before the stop when
    entering on every historical bar. It is included because it is the number this
    signal has to beat — measured so far it sits near the breakeven rate, so the
    geometry alone is not an edge.

    Rendered only with a sufficient sample, and never as the signal's probability of
    success: the walk has no entry rule, so it cannot speak to direction.
    """
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
    # EV / PF / Kelly are all functions of the win rate. The fallbacks computed just
    # above use an assumed rate (0.65/0.55/0.45 by trend), which the platform's own
    # record contradicts — 0 wins in 11 closed trades. So they are shown only when
    # the caller supplied figures derived from a MEASURED rate; otherwise the whole
    # block is dropped and the reason is stated. See services/measured_stats.py.
    metrics_measured = bool(expert and expert.get("metrics_available"))
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
    # Each sentence carries whether it may be dropped when the caption has to be
    # shortened. Optional ones are generic technique that repeats across cards;
    # required ones are risk warnings, sizing, and anything measured. Without
    # this distinction the trim removed the "geometry is unprofitable" warning —
    # the single most important sentence on such a card — while keeping "вход
    # 50% от обычного размера с узким стопом", which is on every other card too.
    parts: list[tuple[str, bool]] = []

    def add(text: str, optional: bool = False) -> None:
        parts.append((text, optional))

    add(f"{name} находится в {trend_ru} "
        f"(изменение за 20 дней: {recent_change:+.1f}%).", optional=True)
    if trend_conflict:
        # Trading against the trend is a risk statement, not advice: it stays.
        add(f"Сигнал на {act_ru} ПРОТИВ текущего тренда — повышенный риск.")
        add(f"Стратегия Mean Reversion: расчёт на отскок от уровня {entry:,.0f}.",
            optional=True)
        add("Рекомендуется уменьшенный размер позиции (25% от обычного) и строгий стоп.")
    elif trend_matches:
        add("Сигнал ПО ТРЕНДУ — моментум подтверждает направление.", optional=True)
        if rr >= 2:
            add(f"R:R {rr:.1f} — отличное соотношение риска к прибыли.", optional=True)
        elif rr >= 1.5:
            add(f"R:R {rr:.1f} — хорошее соотношение.", optional=True)
        add(f"Рекомендуется вход 1-й частью (50%) по рынку, 2-я часть (30%) "
            f"при подтверждении на {entry * 1.02:,.0f}.", optional=True)
    else:
        add(f"Рынок в боковике — сигнал на {act_ru} от уровня "
            f"поддержки/сопротивления.", optional=True)
        add("Рекомендуется вход 50% от обычного размера с узким стопом.", optional=True)
    # Removed: "WEF {wef}% подтверждает качество сигнала по 9 факторам."
    #
    # The score does not confirm quality — that claim is exactly what was tested
    # and failed. Replaying 80 signals against candles put the correlation
    # between score and outcome at -0.35 before the risk_reward fix and +0.07
    # after, i.e. no relationship. The score is a measure of how complete and
    # well-formed the input is; calling it confirmation of quality asserts the
    # one thing the data does not support. The number is already in the header,
    # so nothing is lost by not narrating it — and the ~52 characters are what
    # let the measured geometry baseline fit inside the caption limit instead.
    if rr >= 1.5 and not trend_conflict:
        add(f"Стоп в безубыток после достижения +{tp_pct * 0.4:.1f}%.", optional=True)
    if metrics_measured:
        # Only the part the metrics block above cannot show: what the Kelly
        # percentage means in money. The Profit Factor sentence that used to
        # follow restated a number already printed two lines higher, and those
        # ~90 characters were the difference between the geometry baseline
        # fitting in the caption and being dropped for length.
        add(f"Оптимальный размер по Kelly: {kelly_half:.1f}% от депозита "
            f"({kelly_half * 1000:.0f} на каждые 100 000).")
    else:
        # Why the numbers above are absent. Dropping this would leave the reader
        # to assume they were simply forgotten.
        add((expert or {}).get("metrics_reason")
            or "Мат. ожидание и размер по Kelly не рассчитаны: измеренных "
               "сделок пока недостаточно, а считать их от предполагаемого "
               "win rate значит выдавать допущение за расчёт.")

    # Historical context for the geometry, phrased so it cannot be read as this
    # signal's win probability: the baseline enters on every bar, with no rule.
    if geometry and geometry.get("enough_data"):
        rate = geometry["hit_rate_pct"]
        be = geometry.get("breakeven_pct")
        n = geometry["occurrences"]
        line = (f"История инструмента: при случайном входе цель "
                f"{geometry['tp_mult']:g}×ATR достигалась раньше стопа "
                f"{geometry['sl_mult']:g}×ATR в {rate:.0f}% случаев "
                f"({geometry['reached_target']} из {n}).")
        if be is not None:
            delta = rate - be
            if delta >= 1:
                line += (f" Безубыточная доля для такой геометрии {be:.0f}% — "
                         f"запас {delta:+.0f} п.п.")
            elif delta <= -1:
                line += (f" Безубыточная доля {be:.0f}% — сама геометрия здесь "
                         f"убыточна ({delta:+.0f} п.п.), весь смысл в отборе входа.")
            else:
                line += (f" Это ровно безубыток ({be:.0f}%) — геометрия не даёт "
                         f"преимущества, его должен дать отбор.")
        # Measured evidence about this instrument, and the only sentence that
        # can say the geometry itself is unprofitable. Never optional.
        add(line)

    # The caption goes out as a photo/video caption, where Telegram's limit is
    # 1024 — not the 4096 a plain message gets. Measured before this was added:
    # the card ran 954-989 characters without the geometry line and 1123-1158
    # with it, so EVERY card carrying a geometry baseline was rejected with
    # MEDIA_CAPTION_TOO_LONG. `broadcast_card` logged the failure and returned
    # None, so the signal was simply never published.
    #
    # Trimming happens on `parts`, because these are whole sentences of plain
    # prose with no markup. Cutting the assembled caption instead would land
    # inside an HTML tag and turn a length error into a parse error.
    conclusion = " ".join(text for text, _ in parts)

    price_fmt = ",.2f" if entry >= 1 else ",.5f"
    pyr = "\U0001f53a Пирамидинг: 3 уровня" if not trend_conflict else "\U0001f6ab Пирамидинг: не рекомендуется"

    # Market hashtag for filtering
    market_tag = {"Акции РФ": "MOEX", "Фьючерс": "фьючерсы", "Криптовалюта": "crypto", "Валютная пара": "forex",
                  "Акции": "stocks"}.get(asset_type, "market")
    hashtags = f"#{ticker} #{market_tag} #WinExtraFlow"

    # EV / Profit Factor / Kelly / Edge are all functions of the win rate, so they
    # appear only when that rate was measured. With an assumed rate they read as
    # calculations while being arithmetic on a guess — and the platform's own record
    # (0 wins in 11 closed trades) contradicts the 0.60 that used to be assumed.
    if metrics_measured:
        metrics_block = (
            f"\U0001f4b0 EV: {ev:+.2f}% на сделку\n"
            f"\U0001f4ca Profit Factor: {pf:.2f}\n"
            f"\U0001f3b2 Kelly: {kelly_half:.1f}%\n"
            f"{pyr}\n"
            f"⚡ Edge: {edge:+.1f}%\n\n"
        )
    else:
        metrics_block = f"{pyr}\n\n"

    def assemble(concl: str) -> str:
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
            f"{metrics_block}"
            f"\U0001f4a1 Вывод: {concl}\n\n"
            f"\U0001f4b1 Где торговать: {where}\n"
            f"\U0001f4f2 Полный разбор и WEF Score: {PLATFORM_URL}\n\n"
            f"⚠️ Не является инвестиционной рекомендацией.\n"
            f"{hashtags}"
        )

    caption = assemble(conclusion)
    if len(caption) <= CAPTION_LIMIT:
        return caption

    # Over budget. Drop sentences until it fits, optional ones first and from
    # the end, so generic technique goes before risk warnings and measured
    # evidence. Levels, verdict and the disclaimer sit outside `parts` and are
    # never touched — a card that loses its stop loss to a length limit is worse
    # than no card.
    budget = CAPTION_LIMIT - len(assemble(""))
    keep = [True] * len(parts)

    def size() -> int:
        return len(" ".join(t for (t, _), k in zip(parts, keep) if k))

    for i in range(len(parts) - 1, -1, -1):
        if size() <= budget:
            break
        if parts[i][1]:                      # optional
            keep[i] = False
    for i in range(len(parts) - 1, -1, -1):  # still too long: required ones
        if size() <= budget:
            break
        keep[i] = False

    kept = [t for (t, _), k in zip(parts, keep) if k]

    if not kept:
        # Even one sentence does not fit, which means the fixed part alone is at
        # the limit. Say so rather than shipping a card with an empty verdict.
        logger.warning(f"Caption for {ticker} exceeds {CAPTION_LIMIT} before the "
                       f"conclusion; sending without it")
        return assemble("подробный разбор на платформе")[:CAPTION_LIMIT]

    dropped = len(parts) - len(kept)
    logger.info(f"Caption for {ticker} trimmed: dropped {dropped} of "
                f"{len(parts)} sentences to fit {CAPTION_LIMIT}")
    return assemble(" ".join(kept))


async def broadcast_card(ticker: str, action: str, entry: float, tp: float, sl: float,
                         wef: int, expert: dict | None = None, chat_id: str | None = None,
                         reply_to: int | None = None,
                         geometry: dict | None = None) -> int | None:
    """Render chart + rich caption and send to a channel. Returns the message_id.

    `geometry` was missing here while the clip path passed it, so the same signal
    got a different card depending on whether a video happened to render.
    """
    token = settings.telegram_bot_token
    chat_id = chat_id or settings.telegram_vip_channel_id
    if not token or not chat_id:
        logger.info(f"Chart card skipped (no token/channel) for {ticker}")
        return None

    chart_path, trend, recent_change = await render_chart(ticker, action, entry, tp, sl, wef)
    caption = build_caption(ticker, action, entry, tp, sl, wef, trend, recent_change,
                            expert, geometry=geometry)

    # WEF-based notification: strong signals (>=80%) alert with sound, others silent
    silent = wef < 80

    try:
        async with httpx.AsyncClient(timeout=40) as client:
            if chart_path and os.path.exists(chart_path):
                with open(chart_path, "rb") as f:
                    resp = await client.post(
                        f"https://api.telegram.org/bot{token}/sendPhoto",
                        data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML",
                              "disable_notification": str(silent).lower(),
                              **({"reply_to_message_id": reply_to} if reply_to else {})},
                        files={"photo": (f"chart_{ticker}.png", f, "image/png")},
                    )
            else:
                # No candles — send text-only card
                resp = await client.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": caption, "parse_mode": "HTML",
                          "disable_notification": silent,
                          **({"reply_to_message_id": reply_to} if reply_to else {})},
                )
        data = resp.json()
        ok = data.get("ok", False)
        if not ok:
            logger.error(f"VIP card send failed for {ticker}: {resp.text[:200]}")
            # A photo send can fail for reasons the text send does not share —
            # a caption over the limit, an unreadable image, an upload timeout.
            # The signal still matters, so fall back to text, where the limit is
            # 4096. Without this the whole signal was dropped on the floor.
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": caption[:4096],
                          "parse_mode": "HTML", "disable_notification": silent,
                          **({"reply_to_message_id": reply_to} if reply_to else {})},
                )
            data = resp.json()
            ok = data.get("ok", False)
            logger.info(f"VIP card for {ticker}: text fallback "
                        f"{'succeeded' if ok else 'also failed: ' + resp.text[:160]}")
        return data.get("result", {}).get("message_id") if ok else None
    except Exception as e:
        logger.error(f"VIP card send error for {ticker}: {e}")
        return False
