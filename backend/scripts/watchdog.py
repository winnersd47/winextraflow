"""Watchdog — daily operations report + silent-failure alerts.

The gap this closes: the poller once published wrong data for days and nothing
reported it. This checks that the scheduled jobs actually ran, what the pipeline
produced, and whether external sources are alive — then sends one digest.

Checks:
  1. Job freshness — each scheduled job's log was written recently
  2. Pipeline output (24h) — signals parsed / published / rejected, by reason
  3. Errors — tracebacks / failures in logs
  4. External sources — reuses health_monitor (MOEX, Binance, Yahoo, ...)

Report goes to ADMIN_TELEGRAM_CHAT_ID if set, otherwise printed (and logged).
Get your chat id: message @userinfobot in Telegram, then put it in .env.

Usage:
  python scripts/watchdog.py            # report
  python scripts/watchdog.py --quiet    # only report if there are problems
"""
import asyncio, json, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone
import httpx
from sqlalchemy import select
from app.config import settings
from app.database import async_session
from app.models.signal import Signal, SignalStatus

SCRIPTS = os.path.dirname(os.path.abspath(__file__))

# job label -> (log file, max age in hours before we call it stale)
JOBS = {
    "Парсинг сигналов (30 мин)": ("poller.log", 2),
    "Контроль TP/SL (1 час)":    ("monitor.log", 3),
    "Контент (обзор/дайджест)":  ("content.log", 30),
}


def _log_age_hours(fname: str) -> float | None:
    p = os.path.join(SCRIPTS, fname)
    if not os.path.exists(p):
        return None
    age = datetime.now().timestamp() - os.path.getmtime(p)
    return age / 3600


def _tail(fname: str, n: int = 400) -> list[str]:
    p = os.path.join(SCRIPTS, fname)
    if not os.path.exists(p):
        return []
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.readlines()[-n:]
    except Exception:
        return []


def _count_errors(fname: str) -> tuple[int, str]:
    """Count error markers in the recent tail; return (count, last error line)."""
    pat = re.compile(r"traceback|error|failed|exception", re.IGNORECASE)
    skip = re.compile(r"Live price fetch failed|fetch failed —|regime skipped", re.IGNORECASE)
    hits = [l.strip() for l in _tail(fname) if pat.search(l) and not skip.search(l)]
    return len(hits), (hits[-1][:160] if hits else "")


async def main():
    quiet = "--quiet" in sys.argv
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=24)
    problems: list[str] = []
    lines: list[str] = [f"🩺 <b>Watchdog — {now.strftime('%d.%m.%Y %H:%M')} UTC</b>", ""]

    # ── 1. Job freshness ──
    lines.append("<b>Задачи планировщика:</b>")
    for label, (fname, max_age) in JOBS.items():
        age = _log_age_hours(fname)
        if age is None:
            lines.append(f"  ❔ {label} — лог не найден")
            problems.append(f"{label}: нет лога ({fname})")
        elif age > max_age:
            lines.append(f"  🔴 {label} — не запускалась {age:.1f} ч")
            problems.append(f"{label}: молчит {age:.1f} ч (порог {max_age} ч)")
        else:
            lines.append(f"  ✅ {label} — {age:.1f} ч назад")

    # ── 2. Errors in logs ──
    err_lines = []
    for label, (fname, _) in JOBS.items():
        cnt, last = _count_errors(fname)
        if cnt:
            err_lines.append(f"  ⚠️ {fname}: {cnt} ошибок")
            if last:
                err_lines.append(f"     <code>{last}</code>")
            problems.append(f"{fname}: {cnt} ошибок")
    if err_lines:
        lines += ["", "<b>Ошибки в логах:</b>"] + err_lines

    # ── 3. Pipeline output (24h) ──
    async with async_session() as db:
        recent = (await db.execute(select(Signal).where(Signal.created_at >= since))).scalars().all()
        active = (await db.execute(
            select(Signal).where(Signal.status == SignalStatus.ACTIVE)
        )).scalars().all()

    def flagged(s, *keys):
        r = (s.ai_reasoning or "").lower()
        return any(k in r for k in keys)

    rej_stale = sum(1 for s in recent if flagged(s, "stale entry"))
    rej_quality = sum(1 for s in recent if flagged(s, "quality: rejected", "unrealistic"))
    rej_evo = sum(1 for s in recent if flagged(s, "evolution: skip"))
    published = sum(1 for s in recent if s.ai_confidence and s.ai_confidence >= 0.5)
    closed_tp = sum(1 for s in recent if s.status == SignalStatus.CLOSED_TP)
    closed_sl = sum(1 for s in recent if s.status == SignalStatus.CLOSED_SL)

    lines += ["", "<b>Конвейер за 24 ч:</b>",
              f"  Новых сигналов: {len(recent)}",
              f"  Прошли фильтр: {published}",
              f"  Отклонено: качество {rej_quality} · устаревшие {rej_stale} · стратегия {rej_evo}",
              f"  Закрыто: TP {closed_tp} · SL {closed_sl}",
              f"  Активных сейчас: {len(active)}"]

    if len(recent) == 0:
        problems.append("за 24 ч не появилось ни одного сигнала")
        lines.append("  🔴 Ни одного сигнала за сутки — проверь парсинг")

    # ── 4. External sources ──
    try:
        from app.services.health_monitor import health_monitor
        rep = await health_monitor.check_all()
        icon = {"healthy": "✅", "degraded": "⚠️", "critical": "🔴"}.get(rep["overall"], "❔")
        lines += ["", f"<b>Источники данных:</b> {icon} {rep['overall']}",
                  f"  Живых {rep['healthy']} · деградация {rep['degraded']} · недоступно {rep['down']}"]
        # health_monitor reports "ok" / "degraded" / "down" — only the last two matter
        for key, s in rep["sources"].items():
            if s["status"] in ("down", "degraded"):
                lines.append(f"  {'🔴' if s['status'] == 'down' else '⚠️'} {s['name']}: {s['status']}")
                problems.append(f"источник {s['name']}: {s['status']}")
    except Exception as e:
        lines += ["", f"<b>Источники:</b> проверка не удалась — {e}"]

    # ── verdict ──
    lines.insert(1, "🔴 <b>Есть проблемы</b>" if problems else "✅ <b>Всё работает</b>")
    if problems:
        lines += ["", "<b>Требует внимания:</b>"] + [f"  • {p}" for p in problems[:8]]

    text = "\n".join(lines)

    if quiet and not problems:
        print("OK — no problems, quiet mode, nothing sent")
        return

    chat = getattr(settings, "admin_telegram_chat_id", "") or os.getenv("ADMIN_TELEGRAM_CHAT_ID", "")
    token = settings.telegram_bot_token
    if chat and token:
        body = json.dumps({"chat_id": chat, "text": text, "parse_mode": "HTML",
                           "disable_web_page_preview": True}).encode("utf-8")
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"https://api.telegram.org/bot{token}/sendMessage",
                             content=body, headers={"Content-Type": "application/json; charset=utf-8"})
        print("Sent to admin" if r.json().get("ok") else f"Send failed: {r.text[:160]}")
    else:
        print("(ADMIN_TELEGRAM_CHAT_ID не задан — отчёт только в консоль/лог)\n")

    # Always print so it lands in the log file
    print(re.sub(r"</?(b|code)>", "", text))


asyncio.run(main())
