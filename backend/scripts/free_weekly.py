"""Weekly free-channel post: rejected-signal stats + top-3 by WEF.

Two teasers in one post:
  1. "Что мы НЕ публикуем" — how many signals the quality gate rejected and why
     (proves the filter actually works).
  2. "Топ-3 по WEF" — best signals of the week WITHOUT levels (VIP-exclusive ones
     are named only when they are below the VIP threshold; stronger ones are
     counted, not revealed).

Usage: python scripts/free_weekly.py [--vip]
"""
import asyncio, json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone
import httpx
from sqlalchemy import select
from app.config import settings
from app.database import async_session
from app.models.signal import Signal, SignalStatus

P = "https://winextraflow.pages.dev"


async def main():
    since = datetime.now(timezone.utc) - timedelta(days=7)
    async with async_session() as db:
        rows = (await db.execute(select(Signal).where(Signal.created_at >= since))).scalars().all()

    if not rows:
        print("No signals in the last 7 days — nothing to post."); return

    # ── Rejections: reasons recorded in ai_reasoning by the pipeline/quality gate ──
    def has(s, *keys):
        r = (s.ai_reasoning or "").lower()
        return any(k in r for k in keys)

    rej_quality = sum(1 for s in rows if has(s, "quality: rejected", "quality: weak"))
    rej_rr = sum(1 for s in rows if has(s, "r:r"))
    rej_stale = sum(1 for s in rows if has(s, "stale entry"))
    rej_evo = sum(1 for s in rows if has(s, "evolution: skip"))
    expired = sum(1 for s in rows if s.status == SignalStatus.EXPIRED)
    rejected_total = rej_quality + rej_stale + rej_evo

    published = [s for s in rows if s.ai_confidence and s.ai_confidence >= 0.5]
    strong = [s for s in published if s.ai_confidence >= settings.free_teaser_max_wef / 100]

    lines = [
        "🛡 <b>Что мы НЕ опубликовали на этой неделе</b>",
        f"<i>{since.strftime('%d.%m')} — {datetime.now(timezone.utc).strftime('%d.%m.%Y')}</i>",
        "",
        f"Всего обработано сигналов: <b>{len(rows)}</b>",
        f"Прошли фильтр качества: <b>{len(published)}</b>",
        "",
        "<b>Отклонено:</b>",
    ]
    if rej_quality:
        lines.append(f"  ❌ {rej_quality} — не прошли фильтр (нет TP/SL, WEF ниже 50%)")
    if rej_rr:
        lines.append(f"  ⚖️ {rej_rr} — R:R ниже 1:1.5")
    if rej_stale:
        lines.append(f"  🕰 {rej_stale} — цена входа устарела относительно рынка")
    if rej_evo:
        lines.append(f"  🧬 {rej_evo} — отклонены стратегическим движком")
    if expired:
        lines.append(f"  ⌛ {expired} — истекли, не дойдя до входа")
    if not rejected_total and not rej_rr and not expired:
        lines.append("  — на этой неделе отклонённых нет")

    lines += [
        "",
        "Мы не публикуем сигнал, если он не проходит семь проверок. "
        "Даже если тикер популярный.",
    ]

    # ── Top-3 by WEF (levels never shown here) ──
    top = sorted([s for s in published], key=lambda s: s.ai_confidence, reverse=True)[:3]
    if top:
        lines += ["", "⭐ <b>Топ-3 по WEF Score за неделю</b>", ""]
        for s in top:
            arrow = "🟢" if s.action.value == "buy" else "🔴"
            wef = round(s.ai_confidence * 100)
            locked = " 🔒 VIP" if wef >= settings.free_teaser_max_wef else ""
            lines.append(f"  {arrow} {s.ticker} — WEF {wef}%{locked}")
        lines.append("")
        lines.append("Уровни входа, цели и стопы — в VIP-канале.")

    if strong:
        lines += ["", f"💎 <b>Сигналов с WEF {settings.free_teaser_max_wef}%+ за неделю: {len(strong)}</b>",
                  "Они публикуются только в VIP — в общий канал не попадают."]

    lines += ["", f"🔗 {P}", "",
              "⚠️ Не является инвестиционной рекомендацией.",
              "#статистика #качество #WinExtraFlow"]
    text = "\n".join(lines)

    token = settings.telegram_bot_token
    if not token:
        print("Bot not configured\n\n" + text); return

    targets = [settings.telegram_free_channel_id]
    if "--vip" in sys.argv:
        targets.append(settings.telegram_vip_channel_id)
    for chat in targets:
        if not chat:
            continue
        body = json.dumps({"chat_id": chat, "text": text, "parse_mode": "HTML",
                           "disable_notification": True,
                           "disable_web_page_preview": True}).encode("utf-8")
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"https://api.telegram.org/bot{token}/sendMessage",
                             content=body, headers={"Content-Type": "application/json; charset=utf-8"})
        print(f"{chat}: {'Sent' if r.json().get('ok') else 'Failed: ' + r.text[:140]}")
        await asyncio.sleep(1)


asyncio.run(main())
