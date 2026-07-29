"""Morning market overview -> VIP channel.

BTC price + Fear&Greed + MOEX/crypto snapshot. Posts a daily briefing.
Schedule each morning (e.g. 09:00 MSK).

Usage: python scripts/morning_overview.py
"""
import asyncio, os, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timezone
import httpx
from app.config import settings
from app.services.live_price import get_live_price

PLATFORM = "https://winextraflow.pages.dev"


async def _fear_greed():
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get("https://api.alternative.me/fng/")
            d = r.json()["data"][0]
            return int(d["value"]), d["value_classification"]
    except Exception:
        return None, None


async def main():
    btc = await get_live_price("BTCUSDT")
    eth = await get_live_price("ETHUSDT")
    sber = await get_live_price("SBER")
    fg_val, fg_cls = await _fear_greed()

    def fmt(p, cur=""):
        if not p or not p.get("price"):
            return "н/д"
        ch = p.get("change_pct")
        chs = f" ({ch:+.1f}%)" if ch is not None else ""
        return f"{p['price']:,.2f}{cur}{chs}"

    lines = [
        f"☀️ <b>Утренний обзор — {datetime.now(timezone.utc).strftime('%d.%m.%Y')}</b>",
        "",
        "<b>Крипто:</b>",
        f"  ₿ BTC: {fmt(btc)}",
        f"  Ξ ETH: {fmt(eth)}",
    ]
    if fg_val is not None:
        emoji = "😱" if fg_val < 25 else "😟" if fg_val < 45 else "😐" if fg_val < 55 else "🙂" if fg_val < 75 else "🤑"
        lines.append(f"  {emoji} Индекс страха и жадности: {fg_val} ({fg_cls})")
    lines += ["", "<b>MOEX:</b>", f"  🇷🇺 SBER: {fmt(sber, ' ₽')}"]

    # ── Market regime (what the strategy engine sees today) ──
    try:
        from app.database import async_session
        from app.services.quant.regime import regime_detector
        regime_ru = {
            "trending_up": "восходящий тренд — работаем по тренду",
            "trending_down": "нисходящий тренд — осторожно с покупками",
            "ranging": "боковик — работаем от уровней",
            "high_volatility": "высокая волатильность — уменьшаем размер позиции",
            "low_volatility": "низкая волатильность — точные входы важнее",
            "breakout": "пробой — высокий потенциал",
            "unknown": "режим не определён — стандартные параметры",
        }
        async with async_session() as db:
            st = await regime_detector.detect(db)
        r_key = st.regime.value if hasattr(st.regime, "value") else str(st.regime)
        lines += ["", "<b>Режим рынка:</b>",
                  f"  🧭 {regime_ru.get(r_key, r_key)}",
                  f"  Уверенность: {st.confidence:.0%}"]
    except Exception as e:
        print(f"(regime skipped: {e})")

    lines += ["", f"📲 Сигналы и аналитика дня: {PLATFORM}",
              "", "💎 <b>Сигналы с WEF 70%+ — только в VIP.</b>",
              "", "⚠️ Не является инвестиционной рекомендацией.", "#обзор #WinExtraFlow"]
    text = "\n".join(lines)

    token = settings.telegram_bot_token
    if not token:
        print("Bot not configured\n\n" + text); return
    # Post to BOTH channels — free value for the general audience, context for VIP
    for chat in [settings.telegram_vip_channel_id, settings.telegram_free_channel_id]:
        if not chat:
            continue
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"https://api.telegram.org/bot{token}/sendMessage",
                             json={"chat_id": chat, "text": text, "parse_mode": "HTML",
                                   "disable_notification": True})
        print(f"{chat}: {'Sent' if r.json().get('ok') else 'Failed: ' + r.text[:120]}")
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
