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
from datetime import datetime, timezone

# How long after ingest the staleness rule still applies. Past this, a price far
# from entry means the signal moved, not that it was parsed from old history.
STALE_CHECK_WINDOW_HOURS = 24


def _aware(d):
    """SQLite returns naive datetimes; comparisons against UTC need tzinfo."""
    return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import and_, or_, select
from app.config import settings
from app.database import async_session
from app.models.signal import Signal, SignalStatus, SignalAction
from app.services.live_price import check_signal_status, stale_tolerance
from app.services.signal_quality import SEED_MARKERS, is_seed_signal
from app.services.signal_chart import PLATFORM_URL

TOKEN = os.getenv("BOT_TOKEN", "") or settings.telegram_bot_token

# The stale-entry threshold is per market (see live_price.STALE_TOLERANCE) — 10%
# for everything let week-old crypto signals pass as fresh.
VIP_CHANNEL = os.getenv("VIP_CHANNEL_ID", "") or settings.telegram_vip_channel_id

# Track notified signals to avoid spam
notified = set()


async def _post(chat_id: str, text: str, reply_to: int | None = None) -> int | None:
    """Send one message, optionally threaded as a reply. Returns the message_id."""
    if not TOKEN or not chat_id:
        return None
    body = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
            "disable_notification": True}
    if reply_to:
        # The result belongs under the signal it settles. allow_sending_without_reply
        # keeps the post alive if the original was deleted from the channel.
        body["reply_to_message_id"] = reply_to
        body["allow_sending_without_reply"] = True
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                content=__import__("json").dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
        data = resp.json()
        if not data.get("ok"):
            print(f"  Send failed: {str(data)[:160]}")
            return None
        return data.get("result", {}).get("message_id")
    except Exception as e:
        print(f"  Send error: {e}")
        return None


async def send_free(text: str, reply_to: int | None = None) -> int | None:
    return await _post(settings.telegram_free_channel_id, text, reply_to)


def _result_post(s, pnl: float, won: bool, for_vip: bool) -> str:
    """Result post, published as a reply to the original signal message.

    Wins and losses use the same template. Publishing only take-profits — which is
    what happened before — is selective disclosure: the free channel showed an
    unbroken run of winners while the measured record was 7 trades and no wins.
    Which signals get posted is decided by rating, before the outcome is known; the
    outcome itself never decides whether it is published.
    """
    from app.services.position_sizing import sizing_block
    from app.services.signal_chart import _instrument

    ticker, action = s.ticker, s.action.value
    icon = "✅" if won else "🔻"
    head = "Цель достигнута" if won else "Сработал стоп"
    arrow = "🟢" if action == "buy" else "🔴"
    wef_s = f"{s.ai_confidence:.0%}" if s.ai_confidence else "—"
    _, _, _, currency = _instrument(ticker)
    level = s.take_profit if won else s.stop_loss

    out = [f"{icon} <b>{head}: {ticker}</b>", ""]
    if for_vip:
        out += [f"{arrow} {action.upper()} @ {s.entry_price:g}",
                f"{'Цель' if won else 'Стоп'} {level:g} — {'достигнута' if won else 'сработал'}",
                f"Результат: <b>{pnl:+.1f}%</b>"]
    else:
        out += [f"{arrow} {action.upper()} — результат <b>{pnl:+.1f}%</b>",
                f"WEF Score сигнала: {wef_s}"]

    block = sizing_block(ticker, s.entry_price, s.stop_loss, result_pct=pnl,
                         currency="RUB" if currency == "RUB" else "USD")
    if block:
        out += ["", block]

    if won and s.long_target:
        far = abs(s.long_target - s.entry_price) / s.entry_price * 100
        out += ["", f"🎯 Долгосрочный ориентир источника: {s.long_target:g} "
                    f"({far:+.0f}%) — позиция может держаться дальше."]

    if not for_vip:
        out += ["", "💎 Полный сетап (вход, цель, стоп) был в VIP.",
                "Самые сильные сигналы публикуются только там."]

    out += ["", f"📓 Все сделки, включая убыточные: {PLATFORM_URL}/track-record",
            "⚠️ Не является инвестиционной рекомендацией.", "#результат #WinExtraFlow"]
    return "\n".join(out)


def _publish_result_to_free(s) -> bool:
    """Owner's rule: results of high-rated signals go to the main channel.

    Rating is known before the outcome, so this filter cannot flatter the record.
    Signals that were VIP-exclusive have no teaser in the free channel, so their
    result post simply stands on its own there.
    """
    wef = round((s.ai_confidence or 0) * 100)
    return wef >= settings.free_result_min_wef


async def send_update(text: str):
    """Send update to VIP channel."""
    if not TOKEN or not VIP_CHANNEL:
        print("  BOT_TOKEN / VIP_CHANNEL_ID не заданы — отправка пропущена")
        return
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
        # Exclude seed rows in SQL, not after the LIMIT: they outnumber real
        # signals ~3:1, so a post-filter would leave the limit full of demos.
        not_seed = or_(
            Signal.raw_message.is_(None),
            and_(*[Signal.raw_message.notlike(f"{m}%") for m in SEED_MARKERS]),
        )
        db_signals = (await db.execute(
            select(Signal).where(
                Signal.status == SignalStatus.ACTIVE,
                Signal.take_profit.isnot(None),
                Signal.stop_loss.isnot(None),
                not_seed,
            ).order_by(Signal.created_at.desc()).limit(80)
        )).scalars().all()

        # Seed/demo rows live in the same table. Left in, the monitor would post
        # a generated signal's TP hit to VIP as a real result.
        seeded = [s for s in db_signals if is_seed_signal(s)]
        db_signals = [s for s in db_signals if not is_seed_signal(s)]
        if seeded:
            print(f"Skipping {len(seeded)} seed/demo signals (not real sources)")

        # Age-based write-off. Without it nothing here ever leaves ACTIVE except
        # by hitting a level, now that staleness only applies in the first day.
        from app.services.ai_rating import ai_rating_service
        aged = await ai_rating_service.expire_old_signals(db)
        if aged:
            print(f"Expired {aged} signals older than "
                  f"{settings.signal_expiry_hours}h without reaching a level")

        print(f"Checking {len(db_signals)} active signals...")
        for s in db_signals:
            sig = {"ticker": s.ticker, "action": s.action.value,
                   "entry": s.entry_price, "tp": s.take_profit, "sl": s.stop_loss}
            ticker = s.ticker
            status = await check_signal_status(ticker, sig["action"], sig["entry"], sig["tp"], sig["sl"])
            if not status or status.get("status") == "unknown":
                continue

            live = status.get("current_price") or 0
            action_icon = "🟢" if sig["action"] == "buy" else "🔴"
            # Realized P&L is measured at the TP/SL level, not at the current price.
            tp_pnl = (sig["tp"] - sig["entry"]) / sig["entry"] * 100
            sl_pnl = (sig["sl"] - sig["entry"]) / sig["entry"] * 100
            if sig["action"] == "sell":
                tp_pnl, sl_pnl = -tp_pnl, -sl_pnl

            hit = status["status"]

            # Resolution is checked BEFORE staleness, and that order is the whole
            # point. The staleness rule asks "is the live price far from entry?"
            # — but reaching a target REQUIRES the price to move far from entry.
            # Measured over 150 stored signals, 93% have a target further away
            # than their own staleness tolerance (stocks: 25.1% average target
            # against a 7% limit; MOEX: 44% against 6%). With staleness checked
            # first, every one of those was expired on the way to its target,
            # while a stop — which sits close to entry, inside the tolerance —
            # could always close normally.
            #
            # So the platform could only ever record losses. "0 wins out of 11
            # closed" was not a fact about signal quality; it was this ordering.
            if hit not in ("tp_hit", "sl_hit"):
                # Staleness is a property of INGEST, not of a running signal. The
                # rule exists to catch a signal parsed out of old channel history,
                # whose entry never matched the live market. Applied on every pass
                # it also kills a healthy signal simply for moving toward its own
                # target — which, given the 93% figure above, is nearly all of
                # them. So it only applies while the signal is young: a row whose
                # entry is already far from the market within a day of being
                # ingested came from history. Backfilled messages get created_at
                # at ingest time, so they are correctly caught by this window.
                age_h = (datetime.now(timezone.utc) - _aware(s.created_at)
                         ).total_seconds() / 3600 if s.created_at else 0
                tol = stale_tolerance(ticker)
                if (age_h <= STALE_CHECK_WINDOW_HOURS and live > 0
                        and abs(sig["entry"] - live) / live > tol):
                    s.status = SignalStatus.EXPIRED
                    await db.commit()
                    print(f"  {ticker}: STALE entry {sig['entry']} vs live {live} "
                          f"(limit {tol:.0%}, возраст {age_h:.0f}ч) -> EXPIRED")
                    continue

            if hit in ("tp_hit", "sl_hit"):
                won = hit == "tp_hit"
                pnl = tp_pnl if won else sl_pnl
                s.status = SignalStatus.CLOSED_TP if won else SignalStatus.CLOSED_SL
                s.close_price = sig["tp"] if won else sig["sl"]
                s.profit_pct = pnl
                # Recorded explicitly: the time_decay factor needs the settle time,
                # and updated_at moves whenever any later edit touches the row.
                s.closed_at = datetime.now(timezone.utc)
                await db.commit()
                print(f"  {ticker}: {'TP' if won else 'SL'} HIT -> closed ({pnl:+.1f}%)")

                # This is the path that actually closes signals in production —
                # ai_rating.close_signal is only reached from the API. Without
                # this call the provider aggregates were never recomputed, so
                # win_rate / sharpe / profit_factor / max_drawdown stayed NULL for
                # every provider, and the five WEF factors that read them returned
                # a constant 0.5. That froze 55% of the score's weight.
                from app.services.ai_rating import ai_rating_service
                await ai_rating_service.recalculate_provider_stats(db, s.provider_id)

                # A result is only published for a setup that was published.
                #
                # Without this check the monitor posted outcomes for signals
                # nobody had seen. A source under evaluation — ingested
                # deliberately WITHOUT publishing, so its record could be built
                # before subscribers were shown anything — had its win announced
                # in VIP anyway, as a standalone post with nothing to reply to.
                # That is worse than a missing thread: it publishes a track
                # record for trades the channel never carried, which is the
                # selective disclosure this project removed once already.
                if not s.tg_vip_message_id:
                    print(f"    результат не публикуется: сам сигнал "
                          f"в канал не выходил")
                    await asyncio.sleep(0.1)
                    continue

                # VIP: threaded under the original signal post, so the reader sees
                # the setup and its outcome as one conversation.
                await _post(VIP_CHANNEL, _result_post(s, pnl, won, for_vip=True),
                            reply_to=s.tg_vip_message_id)

                if _publish_result_to_free(s):
                    await send_free(_result_post(s, pnl, won, for_vip=False),
                                    reply_to=s.tg_free_message_id)
                else:
                    print(f"    free channel skipped (WEF below "
                          f"{settings.free_result_min_wef}%)")
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
                f"🔗 {PLATFORM_URL}\n#результат #WinExtraFlow"
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
                f"🔗 {PLATFORM_URL}\n#результат #WinExtraFlow"
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
