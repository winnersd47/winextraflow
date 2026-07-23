"""Weekly performance digest -> VIP channel.

Summarizes the last 7 days of signals: count, avg WEF, by market, top picks.
Builds trust with a public results recap. Schedule weekly (e.g. Sunday).

Usage: python scripts/weekly_digest.py
"""
import asyncio, os, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta, timezone
from collections import Counter
import httpx
from sqlalchemy import select
from app.config import settings
from app.database import async_session
from app.models.signal import Signal
from app.services.backtesting_real import detect_source

PLATFORM = "https://winextraflow.pages.dev"
MARKET_RU = {"moex": "🇷🇺 MOEX", "stocks": "🇺🇸 Акции US", "binance": "₿ Крипто", "forex": "💱 Форекс"}


async def main():
    since = datetime.now(timezone.utc) - timedelta(days=7)
    async with async_session() as db:
        rows = (await db.execute(select(Signal).where(Signal.created_at >= since))).scalars().all()

    if not rows:
        print("No signals in the last 7 days"); return

    by_market = Counter(detect_source(s.ticker) for s in rows)
    wefs = [s.ai_confidence for s in rows if s.ai_confidence]
    avg_wef = round(sum(wefs) / len(wefs) * 100) if wefs else 0
    strong = sum(1 for w in wefs if w >= 0.7)
    # Top 3 by WEF
    top = sorted([s for s in rows if s.ai_confidence], key=lambda s: s.ai_confidence, reverse=True)[:3]

    lines = [
        "📊 <b>Итоги недели — WinExtraFlow</b>",
        f"<i>{since.strftime('%d.%m')} — {datetime.now(timezone.utc).strftime('%d.%m.%Y')}</i>",
        "",
        f"📈 Сигналов: <b>{len(rows)}</b>",
        f"⭐ Средний WEF Score: <b>{avg_wef}%</b>",
        f"🔥 Сильных (WEF≥70%): <b>{strong}</b>",
        "",
        "<b>По рынкам:</b>",
    ]
    for m, n in by_market.most_common():
        lines.append(f"  {MARKET_RU.get(m, m)}: {n}")
    if top:
        lines.append("")
        lines.append("<b>Топ сигналы недели:</b>")
        for s in top:
            arrow = "🟢" if s.action.value == "buy" else "🔴"
            lines.append(f"  {arrow} {s.ticker} — WEF {s.ai_confidence:.0%}")
    lines += ["", f"🔗 Все сигналы и аналитика: {PLATFORM}", "",
              "⚠️ Не является инвестиционной рекомендацией.", "#дайджест #WinExtraFlow"]
    text = "\n".join(lines)

    token = settings.telegram_bot_token
    chat = settings.telegram_vip_channel_id
    if not token or not chat:
        print("Bot not configured\n\n" + text); return
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"https://api.telegram.org/bot{token}/sendMessage",
                         json={"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_notification": True})
    print("Sent" if r.json().get("ok") else f"Failed: {r.text[:200]}")


if __name__ == "__main__":
    asyncio.run(main())
