"""Morning briefing -> VIP and free channels (different text for each).

What changed and why:

* The two channels used to get the identical message, including the line
  "Сигналы с WEF 70%+ — только в VIP" — which was sent TO VIP subscribers,
  telling them the good signals are in the channel they are already reading.
* "WEF 70%+" stopped being true. VIP exclusivity is now `wef >= free_teaser_max_wef`
  OR the top (100 - free_teaser_percentile)% of recent scores, because the absolute
  70 alone covered ~6% of signals and made the promise nearly empty.
* The regime line published a verdict at 24% confidence as a headline. Worse, the
  regime is derived from the platform's own signal flow (regime_detector reads the
  Signal table), not from market data — so in a post about the market it read as a
  claim about the market. It is now labelled for what it is and hidden below a
  confidence floor.
* Percentages had no timeframe. Binance change_pct is a rolling 24h figure; MOEX has
  no change field at all, so it is computed from the session open. Different
  metrics, labelled differently rather than blended.
* Nothing in the briefing could be acted on or checked: no signals, no results, no
  link to the record. It now leads with yesterday's closures and the demo accounts,
  which are facts rather than opinions.

Usage: python scripts/morning_overview.py [--dry]
"""
import asyncio, os, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from app.config import settings
from app.services.live_price import get_live_price
from app.services.signal_chart import PLATFORM_ACCESS_NOTE, PLATFORM_URL

# Below this the regime detector is guessing; publishing the guess as a heading is
# how noise gets presented as insight.
MIN_REGIME_CONFIDENCE = 0.40

MOEX_WATCH = ["SBER", "GAZP", "LKOH"]


async def _fear_greed():
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get("https://api.alternative.me/fng/")
            d = r.json()["data"][0]
            return int(d["value"]), d["value_classification"]
    except Exception:
        return None, None


def _num(v: float, dec: int = 0, signed: bool = False) -> str:
    """Thin space between digit groups — applied to the number only, so it cannot
    eat the punctuation of the surrounding sentence (it did, twice)."""
    s = f"{v:+,.{dec}f}" if signed else f"{v:,.{dec}f}"
    return s.replace(",", " ")


def _fmt(p: dict | None, cur: str = "", window: str = "") -> str:
    """Price with an explicitly labelled change window, or н/д."""
    if not p or not p.get("price"):
        return "н/д"
    ch = p.get("change_pct")
    if ch is None and p.get("open"):
        # MOEX ISS returns no change field — derive it from the session open, and
        # say so, because it is not the same metric as Binance's rolling 24h.
        ch = (p["price"] - p["open"]) / p["open"] * 100
        window = window or "с откр."
    chs = ""
    if ch is not None:
        # Round before formatting, so a -0.04% move does not print as "-0.0%".
        ch = 0.0 if abs(round(ch, 1)) < 0.05 else ch
        chs = f" ({_num(ch, 1, signed=True)}%{' ' + window if window else ''})"
    return f"{_num(p['price'], 2)}{cur}{chs}"


async def gather() -> dict:
    """Everything both briefings draw on. No formatting here."""
    from app.api.track_record import MIN_SAMPLE
    from app.database import async_session
    from app.models.paper import PaperAccount
    from app.models.signal import Signal, SignalStatus
    from app.services.paper_trading import account_stats
    from app.services.signal_quality import is_seed_signal

    out: dict = {"min_sample": MIN_SAMPLE}
    out["btc"] = await get_live_price("BTCUSDT")
    out["eth"] = await get_live_price("ETHUSDT")
    out["moex"] = {t: await get_live_price(t) for t in MOEX_WATCH}
    out["fg_val"], out["fg_cls"] = await _fear_greed()

    day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    async with async_session() as db:
        rows = (await db.execute(select(Signal))).scalars().all()
        real = [s for s in rows if not is_seed_signal(s)]
        out["active"] = sum(1 for s in real if s.status == SignalStatus.ACTIVE)
        closed = [s for s in real if s.status in (SignalStatus.CLOSED_TP,
                                                 SignalStatus.CLOSED_SL)]
        out["closed_total"] = len(closed)
        out["closed_24h"] = [
            {"ticker": s.ticker,
             "won": s.status == SignalStatus.CLOSED_TP,
             "pct": s.profit_pct}
            for s in closed
            if s.updated_at and s.updated_at.replace(tzinfo=timezone.utc) >= day_ago
        ]
        out["new_24h"] = sum(1 for s in real
                             if s.created_at and
                             s.created_at.replace(tzinfo=timezone.utc) >= day_ago)

        try:
            from app.services.quant.regime import regime_detector
            st = await regime_detector.detect(db)
            out["regime"] = (st.regime.value if hasattr(st.regime, "value")
                             else str(st.regime))
            out["regime_conf"] = st.confidence
        except Exception as e:
            print(f"(regime skipped: {e})")
            out["regime"], out["regime_conf"] = None, 0.0

        from app.services.paper_trading import platform_accounts
        accounts = (await db.execute(platform_accounts(select(PaperAccount)))).scalars().all()
        out["paper"] = [await account_stats(db, a) for a in accounts]
    return out


def market_block(d: dict) -> list[str]:
    lines = ["<b>Крипто:</b>",
             f"  ₿ BTC: {_fmt(d['btc'], window='за 24ч')}",
             f"  Ξ ETH: {_fmt(d['eth'], window='за 24ч')}"]
    if d["fg_val"] is not None:
        v = d["fg_val"]
        emoji = "😱" if v < 25 else "😟" if v < 45 else "😐" if v < 55 else "🙂" if v < 75 else "🤑"
        lines.append(f"  {emoji} Индекс страха и жадности: {v} ({d['fg_cls']})")

    lines += ["", "<b>MOEX:</b>"]
    for t in MOEX_WATCH:
        lines.append(f"  🇷🇺 {t}: {_fmt(d['moex'].get(t), ' ₽')}")
    return lines


def flow_block(d: dict) -> list[str]:
    """The regime, honestly labelled — and only when it means something."""
    names = {
        "trending_up": "преобладают покупки",
        "trending_down": "преобладают продажи",
        "ranging": "разнонаправленный",
        "high_volatility": "широкие стопы, размер позиции меньше",
        "low_volatility": "узкие стопы, точность входа важнее",
        "breakout": "много пробойных сетапов",
        "unknown": "не определён",
    }
    if not d["regime"] or d["regime_conf"] < MIN_REGIME_CONFIDENCE:
        return []
    return ["", "<b>Поток сигналов платформы:</b>",
            f"  🧭 {names.get(d['regime'], d['regime'])}",
            f"  Уверенность оценки: {d['regime_conf']:.0%}",
            "  <i>Считается по нашему потоку сигналов, не по рынку.</i>"]


def results_block(d: dict) -> list[str]:
    """Yesterday's closures — wins and losses, because only both are informative."""
    if not d["closed_24h"]:
        return ["", "<b>За сутки:</b>",
                f"  Закрытых сделок нет. Активных сигналов: {d['active']}, "
                f"новых за сутки: {d['new_24h']}."]
    lines = ["", "<b>Закрыто за сутки:</b>"]
    for c in d["closed_24h"]:
        icon = "✅" if c["won"] else "🔻"
        pct = f"{c['pct']:+.1f}%" if c["pct"] is not None else "—"
        lines.append(f"  {icon} {c['ticker']} {pct}")
    lines.append(f"  Активных сигналов: {d['active']}, новых за сутки: {d['new_24h']}")
    return lines


def record_block(d: dict) -> list[str]:
    """The platform's own measured record. The differentiator, so it goes in."""
    lines = ["", "<b>Наш собственный счёт:</b>"]
    for p in d["paper"][:3]:
        sym = "₽" if p["currency"] == "RUB" else "$"
        # "P&amp;L", not "P&L": this post is sent with parse_mode=HTML, where a
        # bare & is the start of an entity. Telegram rejected the entire VIP
        # digest with "can't parse entities" — the script printed a failure line
        # and the cron moved on, so the post simply stopped appearing.
        lines.append(f"  • {p['account']}: открыто {p['open_trades']}, "
                     f"закрыто {p['closed_trades']}, "
                     f"P&amp;L {_num(p['pnl_money'], signed=True)} {sym}")
    if d["closed_total"] < d["min_sample"]:
        lines.append(f"  <i>Измеренных сделок {d['closed_total']} — доходность "
                     f"публикуем от {d['min_sample']}.</i>")
    lines.append(f"  📓 Журнал сделок: {PLATFORM_URL}/track-record")
    return lines


def build_vip(d: dict) -> str:
    head = f"☀️ <b>Утренний обзор — {datetime.now(timezone.utc):%d.%m.%Y}</b>"
    lines = [head, ""] + market_block(d) + flow_block(d) + results_block(d) \
        + record_block(d)
    lines += ["", f"<i>{PLATFORM_ACCESS_NOTE}</i>",
              "", "⚠️ Не является инвестиционной рекомендацией.",
              "#обзор #WinExtraFlow"]
    return "\n".join(lines)


def build_free(d: dict) -> str:
    """Free channel: the same facts, plus what VIP actually gets — stated correctly."""
    head = f"☀️ <b>Утренний обзор — {datetime.now(timezone.utc):%d.%m.%Y}</b>"
    lines = [head, ""] + market_block(d) + results_block(d)
    lines += ["", "<b>Что в VIP:</b>",
              f"  💎 Точки входа, цели и стопы по каждому сигналу",
              f"  💎 Сильнейшие сигналы — верхние "
              f"{100 - settings.free_teaser_percentile}% по WEF Score "
              f"(и всё от {settings.free_teaser_max_wef}%) — публикуются только там",
              f"  📓 Журнал всех сделок, включая убыточные: "
              f"{PLATFORM_URL}/track-record"]
    lines += ["", f"<i>{PLATFORM_ACCESS_NOTE}</i>",
              "", "⚠️ Не является инвестиционной рекомендацией.",
              "#обзор #WinExtraFlow"]
    return "\n".join(lines)


async def main():
    dry = "--dry" in sys.argv
    d = await gather()
    vip_text, free_text = build_vip(d), build_free(d)

    if dry or not settings.telegram_bot_token:
        print("=" * 60 + "\nVIP\n" + "=" * 60 + f"\n{vip_text}\n")
        print("=" * 60 + "\nОБЩИЙ КАНАЛ\n" + "=" * 60 + f"\n{free_text}")
        return

    token = settings.telegram_bot_token
    for chat, text in ((settings.telegram_vip_channel_id, vip_text),
                       (settings.telegram_free_channel_id, free_text)):
        if not chat:
            continue
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"https://api.telegram.org/bot{token}/sendMessage",
                             json={"chat_id": chat, "text": text,
                                   "parse_mode": "HTML",
                                   "disable_notification": True})
        print(f"{chat}: {'Sent' if r.json().get('ok') else 'Failed: ' + r.text[:120]}")
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
