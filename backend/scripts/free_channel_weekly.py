"""Weekly free-channel content: quality-gate report + top signals by WEF.

Two posts that build trust and drive VIP conversion, both from real DB data:
  1. "Что мы НЕ публикуем" — how many signals the quality gate rejected and why.
  2. "Топ по WEF" — the week's strongest signals by score, WITHOUT levels
     (strong ones are VIP-exclusive, so only ticker + score is shown).

Usage: python scripts/free_channel_weekly.py [--vip-too]
"""
import asyncio, os, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone
import httpx
from sqlalchemy import select
from app.config import settings
from app.database import async_session
from app.models.signal import Signal, SignalStatus

PLATFORM = "https://winextraflow.pages.dev"


async def _send(chat_id: str, text: str) -> bool:
    token = settings.telegram_bot_token
    if not token or not chat_id:
        print("(bot not configured)\n" + text)
        return False
    body = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_notification": True}
    data = __import__("json").dumps(body).encode("utf-8")
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"https://api.telegram.org/bot{token}/sendMessage",
                         content=data, headers={"Content-Type": "application/json; charset=utf-8"})
    ok = r.json().get("ok", False)
    print("sent" if ok else f"failed: {r.text[:160]}")
    return ok


async def main():
    since = datetime.now(timezone.utc) - timedelta(days=7)
    async with async_session() as db:
        rows = (await db.execute(select(Signal).where(Signal.created_at >= since))).scalars().all()

    if not rows:
        print("No signals in the last 7 days"); return

    # ── 1. Quality-gate report ──
    reasons = {"low_rr": 0, "low_wef": 0, "no_levels": 0, "stale": 0, "skip": 0}
    published = 0
    for s in rows:
        note = (s.ai_reasoning or "").lower()
        if "stale entry" in note:
            reasons["stale"] += 1
        elif "evolution: skip" in note:
            reasons["skip"] += 1
        elif not s.take_profit or not s.stop_loss:
            reasons["no_levels"] += 1
        elif s.ai_confidence is not None and s.ai_confidence < 0.5:
            reasons["low_wef"] += 1
        else:
            rr = 0
            if s.take_profit and s.stop_loss and s.entry_price:
                risk = abs(s.entry_price - s.stop_loss)
                rr = abs(s.take_profit - s.entry_price) / risk if risk else 0
            if rr and rr < 1.5:
                reasons["low_rr"] += 1
            else:
                published += 1
    rejected = sum(reasons.values())

    lines = [
        "🛡 <b>Что мы НЕ публикуем</b>",
        f"<i>за последние 7 дней</i>", "",
        f"Обработано сигналов: <b>{len(rows)}</b>",
        f"Прошли фильтр качества: <b>{published}</b>",
        f"Отклонено: <b>{rejected}</b>", "",
        "<b>Причины отказа:</b>",
    ]
    labels = {
        "low_rr": "R:R ниже 1:1.5 — риск не оправдан",
        "low_wef": "WEF Score ниже 50%",
        "no_levels": "нет цели или стопа",
        "stale": "цена входа оторвана от рынка",
        "skip": "стратегия против тренда",
    }
    for k, n in sorted(reasons.items(), key=lambda x: -x[1]):
        if n:
            lines.append(f"  • {labels[k]}: <b>{n}</b>")
    lines += [
        "",
        "Мы не шлём всё подряд. Каждый сигнал проходит 7 проверок: "
        "наличие TP/SL, R:R, WEF Score, история провайдера, дубли, направление, актуальность цены.",
        "",
        f"💎 <b>Сигналы с WEF 70%+ публикуются только в VIP.</b>",
        f"🔗 {PLATFORM}", "",
        "⚠️ Не является инвестиционной рекомендацией.",
        "#качество #WinExtraFlow",
    ]
    gate_text = "\n".join(lines)

    # ── 2. Top by WEF (no levels — strong ones are VIP-only) ──
    scored = [s for s in rows if s.ai_confidence]
    top = sorted(scored, key=lambda s: s.ai_confidence, reverse=True)[:3]
    t_lines = ["🏆 <b>Топ сигналов недели по WEF Score</b>", ""]
    for i, s in enumerate(top, 1):
        arrow = "🟢" if s.action.value == "buy" else "🔴"
        medal = ["🥇", "🥈", "🥉"][i - 1]
        t_lines.append(f"{medal} {arrow} <b>{s.ticker}</b> — WEF <b>{s.ai_confidence:.0%}</b>")
    avg = round(sum(s.ai_confidence for s in scored) / len(scored) * 100) if scored else 0
    t_lines += [
        "", f"Средний WEF за неделю: <b>{avg}%</b>",
        "",
        "Уровни входа, цели и стопы по этим сигналам — в VIP-канале.",
        "💎 <b>Всё, что выше 70%, в общий канал не попадает.</b>",
        "", f"🔗 {PLATFORM}", "",
        "⚠️ Не является инвестиционной рекомендацией.",
        "#топнедели #WinExtraFlow",
    ]
    top_text = "\n".join(t_lines)

    free = settings.telegram_free_channel_id
    print("=== quality gate report ==="); await _send(free, gate_text)
    await asyncio.sleep(2)
    print("=== top by WEF ==="); await _send(free, top_text)

    if "--vip-too" in sys.argv and settings.telegram_vip_channel_id:
        await asyncio.sleep(2)
        await _send(settings.telegram_vip_channel_id, gate_text)


asyncio.run(main())
