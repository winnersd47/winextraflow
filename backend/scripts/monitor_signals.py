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
from app.services.live_price import check_signal_status


# Active signals to monitor (in production: load from DB)
ACTIVE_SIGNALS = [
    {"ticker": "SBER", "action": "buy", "entry": 296.77, "tp": 315.29, "sl": 287.51},
    {"ticker": "GAZP", "action": "sell", "entry": 98.35, "tp": 88.09, "sl": 104.21},
    {"ticker": "LKOH", "action": "sell", "entry": 4145, "tp": 3595, "sl": 4459},
    {"ticker": "EURUSD", "action": "buy", "entry": 1.13598, "tp": 1.1502, "sl": 1.12886},
    {"ticker": "NVDA", "action": "sell", "entry": 199, "tp": 177, "sl": 212},
]

TOKEN = os.getenv("BOT_TOKEN", "8942312432:AAH2veIFPzRiJIavz9VuG2ILgk3AUY7HaHU")
VIP_CHANNEL = os.getenv("VIP_CHANNEL_ID", "-1003914705738")

# Track notified signals to avoid spam
notified = set()


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
    """Check all active signals against live prices."""
    print(f"\n{'='*50}")
    print(f"Signal Monitor — {__import__('datetime').datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*50}")

    for sig in ACTIVE_SIGNALS:
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
                f"Сигнал закрыт с прибылью."
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
                f"Сигнал закрыт по стопу."
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
