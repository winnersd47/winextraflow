"""Put a channel on trial: ingest and measure it, never publish it.

A new source cannot be judged before it has a record, and it cannot get a record
without being traded. Publishing it to find out means finding out with
subscribers watching. So a trial source is parsed, scored and opened on the
"Оценка новых источников" paper account, and nothing it produces reaches a
channel until it has MIN_SAMPLE closed trades of its own.

The forex channels this was written for need 67-87% of trades to win just to
break even (scripts/find_forex_sources.py prints the figure). The platform's own
record is 0 wins in 10. Neither number says what the other will be.

Usage:
    python scripts/add_trial_source.py --list
    python scripts/add_trial_source.py forex_vip_signals "Forex VIP Signals"
    python scripts/add_trial_source.py --promote forex_vip_signals   # start publishing
    python scripts/add_trial_source.py --drop forex_vip_signals
"""
import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.database import async_session
from app.models.paper import PaperAccount, PaperTrade, PaperTradeStatus
from app.models.provider import Provider, ProviderSource
from app.models.signal import Signal, SignalStatus


async def report(db) -> None:
    provs = (await db.execute(
        select(Provider).where(Provider.paper_only.is_(True))
    )).scalars().all()
    if not provs:
        print("Источников на оценке нет.")
        return

    from app.services.measured_stats import MIN_SAMPLE

    acc = (await db.execute(
        select(PaperAccount).where(PaperAccount.scope == "evaluation")
    )).scalar_one_or_none()

    print(f"{'источник':<34}{'сигналов':>9}{'закрыто':>9}{'побед':>7}  статус")
    print("-" * 74)
    for p in provs:
        sigs = (await db.execute(
            select(Signal).where(Signal.provider_id == p.id)
        )).scalars().all()
        closed = [s for s in sigs if s.status in (SignalStatus.CLOSED_TP,
                                                  SignalStatus.CLOSED_SL)]
        wins = sum(1 for s in closed if s.status == SignalStatus.CLOSED_TP)
        if len(closed) < MIN_SAMPLE:
            status = f"нужно ещё {MIN_SAMPLE - len(closed)} закрытых"
        else:
            status = f"готов к решению — win rate {wins / len(closed) * 100:.0f}%"
        print(f"{p.name[:33]:<34}{len(sigs):>9}{len(closed):>9}{wins:>7}  {status}")

    if acc:
        trades = (await db.execute(
            select(PaperTrade).where(PaperTrade.account_id == acc.id)
        )).scalars().all()
        done = [t for t in trades if t.status in (PaperTradeStatus.CLOSED_TP,
                                                  PaperTradeStatus.CLOSED_SL)]
        pnl = sum(t.result_money or 0 for t in done)
        print("-" * 74)
        print(f"Счёт «{acc.name}»: баланс {acc.balance:,.0f} {acc.currency}, "
              f"открыто {sum(1 for t in trades if t.status == PaperTradeStatus.OPEN)}, "
              f"закрыто {len(done)}, P&L {pnl:+,.0f}".replace(",", " "))
    print("\nПока источник здесь, его сигналы не попадают ни в один канал\n"
          "и не входят в измеренный рекорд платформы.")


async def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}

    async with async_session() as db:
        if "--list" in flags or not args:
            await report(db)
            return 0

        username = args[0].lstrip("@")
        title = args[1] if len(args) > 1 else username

        prov = (await db.execute(
            select(Provider).where(Provider.telegram_channel_id == username)
        )).scalar_one_or_none()
        if prov is None:
            prov = (await db.execute(
                select(Provider).where(Provider.name == title)
            )).scalar_one_or_none()

        if "--drop" in flags:
            if not prov:
                print(f"@{username} не найден")
                return 1
            prov.paper_only = False
            prov.is_active = False
            await db.commit()
            print(f"@{username} отключён (is_active=False).")
            return 0

        if "--promote" in flags:
            if not prov:
                print(f"@{username} не найден")
                return 1
            from app.services.measured_stats import MIN_SAMPLE
            closed = [s for s in (await db.execute(
                select(Signal).where(Signal.provider_id == prov.id)
            )).scalars().all()
                if s.status in (SignalStatus.CLOSED_TP, SignalStatus.CLOSED_SL)]
            if len(closed) < MIN_SAMPLE:
                # Refusing here is the whole point: promoting early turns the
                # trial into a formality.
                print(f"Отказ: закрытых сделок {len(closed)}, нужно {MIN_SAMPLE}. "
                      f"До этого о источнике ничего не измерено.")
                return 1
            wins = sum(1 for s in closed if s.status == SignalStatus.CLOSED_TP)
            prov.paper_only = False
            await db.commit()
            print(f"@{username} переведён в публикацию. "
                  f"Измерено: {wins}/{len(closed)} побед "
                  f"({wins / len(closed) * 100:.0f}%).")
            return 0

        if prov:
            prov.paper_only = True
            prov.is_active = True
            prov.telegram_channel_id = username
            await db.commit()
            print(f"@{username} переведён на оценку.")
        else:
            db.add(Provider(name=title, source=ProviderSource.TELEGRAM,
                            telegram_channel_id=username,
                            description=f"На оценке: @{username}",
                            is_active=True, paper_only=True))
            await db.commit()
            print(f"@{username} добавлен как источник на оценке.")

        # Register it where the poller actually looks. `load_monitored` reads
        # monitored_channels.json and only falls back to TELEGRAM_PARSE_CHANNELS
        # when that file does not exist — so the previous advice, "add it to
        # .env", was advice that silently did nothing. Three forex channels sat
        # in .env for a week while the poller never read one message from them.
        from app.services.channel_discovery import load_monitored, save_monitored

        watched = load_monitored()
        if username not in watched:
            save_monitored(watched + [username])
            print(f"\n@{username} добавлен в monitored_channels.json — "
                  f"поллер прочитает его со следующего прогона.")
        else:
            print(f"\n@{username} уже в списке поллера.")
        return 0


sys.exit(asyncio.run(main()))
