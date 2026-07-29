"""Monitor active signals — check if TP or SL hit, send updates to VIP.

Usage:
    python scripts/monitor_signals.py              # check all active signals once
    python scripts/monitor_signals.py --loop 300    # check every 5 minutes

Sends Telegram update when:
- TP hit → profit notification
- SL hit → stop loss notification
- Price moved > 50% to TP or SL → progress update
"""

import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import select
from app.config import settings
from app.database import async_session
from app.models.signal import Signal, SignalStatus, SignalAction
from app.services.live_price import check_signal_status

TOKEN = os.getenv("BOT_TOKEN", "") or settings.telegram_bot_token or "8942312432:AAH2veIFPzRiJIavz9VuG2ILgk3AUY7HaHU"

# If a signal's entry deviates from the live price by more than this, it is stale
# (parsed from old channel history) — expire it instead of reporting fake P&L.
STALE_ENTRY_TOLERANCE = 0.10  # 10%
VIP_CHANNEL = os.getenv("VIP_CHANNEL_ID", "-1003914705738")

# Track notified signals to avoid spam
notified = set()


async def send_free(text: str):
    """Send a result teaser to the free channel (proof of work -> VIP conversion)."""
    chan = settings.telegram_free_channel_id
    if not chan:
        return
    try:
        body = {"chat_id": chan, "text": text, "parse_mode": "HTML", "disable_notification": True}
        body_bytes = __import__("json").dumps(body).encode("utf-8")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                content=body_bytes,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
            if resp.json().get("ok"):
                print("  Sent result teaser to free channel")
    except Exception as e:
        print(f"  Free send error: {e}")


async def send_update(text: str):
    """Send update to VIP channel."""
    try:
        body = {"chat_id": VIP_CHANNEL, "text": text, "parse_mode": "HTML", "disable_notification": True}
        body_bytes = __import__("json").dumps(body).encode("utf-8")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                content=body_bytes,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
            result = resp.json()
            if result.get("ok"):
                print(f"  Sent update to VIP")
            else:
                print(f"  Send failed: {result}")
    except Exception as e:
        print(f"  Send error: {e}")


async def check_all():
    """Check all ACTIVE DB signals against live prices; close + notify on TP/SL hit."""
    print(f"\n{'='*50}")
    print(f"Signal Monitor — {__import__('datetime').datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*50}")

    async with async_session() as db:
        db_signals = (await db.execute(
            select(Signal).where(
                Signal.status == SignalStatus.ACTIVE,
                Signal.take_profit.isnot(None),
                Signal.stop_loss.isnot(None),
            ).order_by(Signal.created_at.desc()).limit(80)
        )).scalars().all()

        print(f"Checking {len(db_signals)} active signals...")
        for s in db_signals:
            sig = {"ticker": s.ticker, "action": s.action.value,
                   "entry": s.entry_price, "tp": s.take_profit, "sl": s.stop_loss}
            ticker = s.ticker
            status = await check_signal_status(ticker, sig["action"], sig["entry"], sig["tp"], sig["sl"])
            if not status or status.get("status") == "unknown":
                continue

            live = status.get("current_price") or 0
            # Sanity: an entry far from the live market means a stale/bad signal.
            # Expire it silently instead of claiming a huge profit/loss.
            if live > 0 and abs(sig["entry"] - live) / live > STALE_ENTRY_TOLERANCE:
                s.status = SignalStatus.EXPIRED
                await db.commit()
                print(f"  {ticker}: STALE entry {sig['entry']} vs live {live} -> EXPIRED (no post)")
                continue

            action_icon = "🟢" if sig["action"] == "buy" else "🔴"
            # Realized P&L is measured at the TP/SL level, not at the current price.
            tp_pnl = (sig["tp"] - sig["entry"]) / sig["entry"] * 100
            sl_pnl = (sig["sl"] - sig["entry"]) / sig["entry"] * 100
            if sig["action"] == "sell":
                tp_pnl, sl_pnl = -tp_pnl, -sl_pnl

            if status["status"] == "tp_hit":
                s.status = SignalStatus.CLOSED_TP
                await db.commit()
                await send_update(
                    f"🟢 TAKE PROFIT {ticker}!\n\n{action_icon} {sig['action'].upper()} @ {sig['entry']}\n"
                    f"TP: {sig['tp']} — ДОСТИГНУТ\nПрибыль: {tp_pnl:+.1f}%\n\n"
                    f"Сигнал закрыт с прибылью.\n🔗 https://winextraflow.pages.dev\n#результат #WinExtraFlow"
                )
                print(f"  {ticker}: TP HIT -> closed ({tp_pnl:+.1f}%)")
                # Result teaser for the free channel — proof the signals work,
                # without revealing the entry/TP levels themselves.
                wef_s = f"{s.ai_confidence:.0%}" if s.ai_confidence else "—"
                await send_free(
                    f"✅ <b>Цель достигнута: {ticker}</b>\n\n"
                    f"{action_icon} {sig['action'].upper()} — результат <b>{tp_pnl:+.1f}%</b>\n"
                    f"WEF Score сигнала: {wef_s}\n\n"
                    f"💎 Этот сигнал был в VIP с точкой входа, целью и стопом.\n"
                    f"<b>Сигналы с WEF 70%+ публикуются только в VIP.</b>\n\n"
                    f"🔗 https://winextraflow.pages.dev\n"
                    f"⚠️ Не является инвестиционной рекомендацией.\n#результат #WinExtraFlow"
                )
            elif status["status"] == "sl_hit":
                s.status = SignalStatus.CLOSED_SL
                await db.commit()
                await send_update(
                    f"🔴 STOP LOSS {ticker}!\n\n{action_icon} {sig['action'].upper()} @ {sig['entry']}\n"
                    f"SL: {sig['sl']} — СРАБОТАЛ\nУбыток: {sl_pnl:+.1f}%\n\n"
                    f"Сигнал закрыт по стопу.\n🔗 https://winextraflow.pages.dev\n#результат #WinExtraFlow"
                )
                print(f"  {ticker}: SL HIT -> closed ({sl_pnl:+.1f}%)")
            else:
                print(f"  {ticker}: active ({status['pnl_pct']:+.1f}%)")
            await asyncio.sleep(0.1)
    return


async def _legacy_unused():
    """kept for reference — old in-memory flow below is disabled."""
    for sig in []:
        ticker = sig["ticker"]
        status = await check_signal_status(ticker, sig["action"], sig["entry"], sig["tp"], sig["sl"])

        if not status or status.get("status") == "unknown":
            print(f"  {ticker}: price unavailable")
            continue

        icon = {"active": "🔵", "tp_hit": "🟢", "sl_hit": "🔴"}.get(status["status"], "⚪")
        action_icon = "🟢" if sig["action"] == "buy" else "🔴"

        print(f"  {icon} {ticker} {sig['action'].upper()} @ {sig['entry']} → {status['current_price']} "
              f"| P&L: {status['pnl_pct']:+.2f}% | TP: {status['distance_to_tp_pct']:.1f}% away | SL: {status['distance_to_sl_pct']:.1f}% away")

        # TP hit
        if status["status"] == "tp_hit" and f"{ticker}_tp" not in notified:
            notified.add(f"{ticker}_tp")
            text = (
                f"🟢 TAKE PROFIT {ticker}!\n\n"
                f"{action_icon} {sig['action'].upper()} @ {sig['entry']}\n"
                f"TP: {sig['tp']} — ДОСТИГНУТ\n"
                f"Прибыль: {status['pnl_pct']:+.1f}%\n\n"
                f"Сигнал закрыт с прибылью.\n"
                f"🔗 https://winextraflow.pages.dev\n#результат #WinExtraFlow"
            )
            await send_update(text)

        # SL hit
        elif status["status"] == "sl_hit" and f"{ticker}_sl" not in notified:
            notified.add(f"{ticker}_sl")
            text = (
                f"🔴 STOP LOSS {ticker}!\n\n"
                f"{action_icon} {sig['action'].upper()} @ {sig['entry']}\n"
                f"SL: {sig['sl']} — СРАБОТАЛ\n"
                f"Убыток: {status['pnl_pct']:+.1f}%\n\n"
                f"Сигнал закрыт по стопу.\n"
                f"🔗 https://winextraflow.pages.dev\n#результат #WinExtraFlow"
            )
            await send_update(text)

        # Progress update: price moved > 50% to TP
        elif status["status"] == "active":
            total_distance = abs(sig["tp"] - sig["entry"])
            current_progress = abs(status["current_price"] - sig["entry"])
            progress_pct = (current_progress / total_distance * 100) if total_distance > 0 else 0

            if progress_pct > 50 and status["pnl_pct"] > 0 and f"{ticker}_50" not in notified:
                notified.add(f"{ticker}_50")
                text = (
                    f"📊 Обновление {ticker}\n\n"
                    f"{action_icon} {sig['action'].upper()} @ {sig['entry']}\n"
                    f"Текущая: {status['current_price']} ({status['pnl_pct']:+.1f}%)\n"
                    f"Прогресс к TP: {progress_pct:.0f}%\n\n"
                    f"Рекомендация: перевод стопа в безубыток."
                )
                await send_update(text)


async def main():
    args = sys.argv[1:]

    if "--loop" in args:
        idx = args.index("--loop")
        interval = int(args[idx + 1]) if idx + 1 < len(args) else 300
        print(f"Monitoring loop: every {interval}s ({interval//60} min)")
        while True:
            await check_all()
            await asyncio.sleep(interval)
    else:
        await check_all()


if __name__ == "__main__":
    asyncio.run(main())
