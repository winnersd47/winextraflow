"""Watchdog — daily operations report + silent-failure alerts.

The gap this closes: the poller once published wrong data for days and nothing
reported it. This checks that the scheduled jobs actually ran, what the pipeline
produced, and whether external sources are alive — then sends one digest.

Checks:
  1. Job freshness — each scheduled job's log was written recently
  2. Pipeline output (24h) — signals parsed / published / rejected, by reason
  3. Errors — tracebacks / failures in logs
  4. External sources — reuses health_monitor (MOEX, Binance, Yahoo, ...)

Delivery: bot DM to ADMIN_TELEGRAM_CHAT_ID if set, otherwise the operator's own
Telegram Saved Messages via the authorized user session. --quiet still sends one
report every 20h, because a watchdog that is silent when healthy looks exactly
like a watchdog that died. Exits 1 when problems are found so the scheduler
records a failed run.

Usage:
  python scripts/watchdog.py            # full report
  python scripts/watchdog.py --quiet    # problems only, plus a daily heartbeat
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


# A completed run writes this line. Everything after the last one belongs to the
# newest run, which is the only thing worth alarming about.
RUN_END = re.compile(r"Backfill complete:|=== (?:Done|Finished)", re.IGNORECASE)


def _last_run(lines: list[str]) -> list[str]:
    """Only the lines written after the most recent completed run.

    Without this the counter read a 400-line tail regardless of age, so errors
    stayed "current" long after they were fixed. That matters more than it
    sounds: this watchdog reported `poller.log: 25 ошибок` from a revoked auth
    key for as long as those lines sat in the tail, including after the key was
    replaced and the pipeline was healthy again. An alarm that stays red once
    the fault is gone teaches its reader to ignore it — which is how a 37-day
    outage went unnoticed in the first place.
    """
    for i in range(len(lines) - 1, -1, -1):
        if RUN_END.search(lines[i]):
            return lines[i + 1:]
    return lines


def _count_errors(fname: str) -> tuple[int, str]:
    """Errors in the newest run only; returns (count, last error line)."""
    pat = re.compile(r"traceback|error|failed|exception", re.IGNORECASE)
    skip = re.compile(r"Live price fetch failed|fetch failed —|regime skipped", re.IGNORECASE)
    recent = _last_run(_tail(fname))
    hits = [l.strip() for l in recent if pat.search(l) and not skip.search(l)]
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

    # Quiet mode still sends one report a day. A watchdog that only speaks up on
    # failure is indistinguishable from a watchdog that stopped running, so the
    # daily "всё работает" is what makes silence meaningful.
    if quiet and not problems and not _heartbeat_due():
        print("OK — no problems, heartbeat already sent today, nothing to send")
        return

    # Always print first so the report survives even if delivery fails.
    print(re.sub(r"</?(b|code)>", "", text))

    if await _deliver(text):
        _mark_heartbeat()
    else:
        print("!! Отчёт НЕ доставлен — ни бот, ни аккаунт Telegram недоступны")
        # Name the actual cause. Both delivery paths failing looks like one
        # outage, but they fail for unrelated reasons and only one of them is
        # fixable in thirty seconds. Worse, the account path uses the same
        # Telethon session as the signal poller — so the watchdog goes mute in
        # exactly the situation it exists to report, which is how a dead
        # pipeline stayed unnoticed for a month.
        chat = (getattr(settings, "admin_telegram_chat_id", "")
                or os.getenv("ADMIN_TELEGRAM_CHAT_ID", ""))
        if not chat:
            print("   Причина: ADMIN_TELEGRAM_CHAT_ID не задан, поэтому бот не "
                  "знает, куда писать.")
            print("   Бот при этом рабочий — путь через аккаунт не нужен, если "
                  "задать chat id:")
            print("       python scripts/tg_find_admin_chat.py")
            print("   Пока он пуст, единственный канал доставки — Telethon-"
                  "сессия, та же самая,")
            print("   которой читаются каналы. Ломается она — сторож замолкает "
                  "вместе с конвейером.")

    # Non-zero exit so Task Scheduler / cron records the run as failed.
    if problems:
        sys.exit(1)


HEARTBEAT_FILE = os.path.join(SCRIPTS, "watchdog_heartbeat.txt")


def _heartbeat_due() -> bool:
    try:
        with open(HEARTBEAT_FILE) as f:
            last = datetime.fromisoformat(f.read().strip())
    except Exception:
        return True
    return (datetime.now(timezone.utc) - last) >= timedelta(hours=20)


def _mark_heartbeat() -> None:
    try:
        with open(HEARTBEAT_FILE, "w") as f:
            f.write(datetime.now(timezone.utc).isoformat())
    except OSError:
        pass


async def _deliver(text: str) -> bool:
    """Send the report to the operator. Bot DM first, then own Telegram account.

    The bot can only DM a chat id we already know, and it was never set, so every
    report used to end up in a log file nobody reads. The authorized user session
    can always write to Saved Messages, which needs no chat id at all.
    """
    chat = getattr(settings, "admin_telegram_chat_id", "") or os.getenv("ADMIN_TELEGRAM_CHAT_ID", "")
    token = settings.telegram_bot_token
    if chat and token:
        try:
            body = json.dumps({"chat_id": chat, "text": text, "parse_mode": "HTML",
                               "disable_web_page_preview": True}).encode("utf-8")
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.post(f"https://api.telegram.org/bot{token}/sendMessage",
                                 content=body, headers={"Content-Type": "application/json; charset=utf-8"})
            if r.json().get("ok"):
                print("Отчёт отправлен админу (бот)")
                return True
            print(f"Бот не смог отправить: {r.text[:160]}")
        except Exception as e:
            print(f"Бот не смог отправить: {e}")

    return await _deliver_via_account(text)


async def _deliver_via_account(text: str) -> bool:
    """Write the report into the operator's own Saved Messages via Telethon."""
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        return False
    try:
        # The session is NOT copied any more. Copying a .session file copies the
        # auth key, and Telegram revokes a key it sees connect from two places:
        # that is how this watchdog helped kill the pipeline it was watching.
        # Every session file on disk held the identical key afterwards, and the
        # outage ran 37 days unnoticed because the alarm had silenced itself.
        #
        # The lock makes this wait for the poller instead of cloning around it.
        from app.services.telethon_lock import telethon_session

        async with telethon_session("wef_backfill", timeout=60) as client:
            if client is None:
                print("Telethon занят поллером — отчёт через аккаунт пропущен")
                return False
            if not await client.is_user_authorized():
                print("Telegram-аккаунт не авторизован — отчёт не отправлен")
                return False
            await client.send_message("me", text, parse_mode="html",
                                      link_preview=False)
            print("Отчёт отправлен в Saved Messages (аккаунт)")
            return True
    except Exception as e:
        print(f"Отправка через аккаунт не удалась: {e}")
        return False


asyncio.run(main())
