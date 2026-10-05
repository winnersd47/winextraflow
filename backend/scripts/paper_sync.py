"""Open/settle virtual positions for every published signal.

Run on the same schedule as the signal monitor: the monitor decides that a signal
closed, this turns that into a recorded trade with money attached.

Usage:
    python scripts/paper_sync.py            # one cycle, print the report
    python scripts/paper_sync.py --trades   # also list the closed trades
"""
import asyncio, os, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import async_session
from app.models.paper import PaperTrade, PaperTradeStatus
from app.services.paper_trading import platform_trades, run_all


async def main():
    show_trades = "--trades" in sys.argv
    async with async_session() as db:
        report = await run_all(db)

        for r in report:
            sym = "₽" if r["currency"] == "RUB" else "$"
            print(f"\n{'='*62}")
            filt = f", только WEF >= {r['min_wef']}%" if r["min_wef"] else ""
            print(f"{r['account']}  (риск {r['risk_per_trade_pct']}%{filt})")
            print(f"{'='*62}")
            print(f"  Открыто сейчас: +{r['opened_now']}   "
                  f"закрыто: +{r['closed_now']}   отменено: +{r['cancelled_now']}")
            print(f"  Позиций открыто: {r['open_trades']}   "
                  f"закрытых сделок: {r['closed_trades']}   "
                  f"отменённых: {r['cancelled_trades']}")
            def m(v, signed=False):
                return (f"{v:+,.0f}" if signed else f"{v:,.0f}").replace(",", " ")
            print(f"  Баланс: {m(r['balance'])} {sym} "
                  f"(старт {m(r['starting_balance'])} {sym}, "
                  f"P&L {m(r['pnl_money'], True)} {sym} / {r['pnl_pct_of_start']:+.2f}%)")
            if r["enough_data"]:
                print(f"  Win rate: {r['win_rate_pct']}%   "
                      f"средний результат: {r['avg_result_pct']}%   "
                      f"profit factor: {r['profit_factor']}")
            else:
                print(f"  {r['notice_ru']}")

        if show_trades:
            rows = (await db.execute(
                platform_trades(select(PaperTrade)).where(PaperTrade.status.in_(
                    (PaperTradeStatus.CLOSED_TP, PaperTradeStatus.CLOSED_SL)
                )).order_by(PaperTrade.closed_at.desc()).limit(30)
            )).scalars().all()
            if rows:
                print(f"\n{'='*62}\nПоследние закрытые сделки\n{'='*62}")
                for t in rows:
                    mark = "TP" if t.status == PaperTradeStatus.CLOSED_TP else "SL"
                    print(f"  {t.ticker:<10} {t.action:<4} {mark}  "
                          f"{t.result_pct:+6.2f}%  {t.result_money:+9.0f}  "
                          f"WEF {t.wef_at_open or 0}%")


asyncio.run(main())
