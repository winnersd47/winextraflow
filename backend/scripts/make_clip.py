"""Generate (and optionally send) a signal video clip.

Usage:
  python scripts/make_clip.py SBER buy 300 330 285 71            # render only
  python scripts/make_clip.py SBER buy 300 330 285 71 --send     # + send to VIP
  python scripts/make_clip.py SBER buy 300 330 285 71 --send --free  # + teaser to free
"""
import asyncio, os, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.services.signal_clip import make_clip, broadcast_clip


async def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if len(a) < 5:
        print(__doc__); return
    ticker, action = a[0].upper(), a[1].lower()
    entry, tp, sl = float(a[2]), float(a[3]), float(a[4])
    wef = int(a[5]) if len(a) > 5 else 70
    verdict = "ХОРОШИЙ" if wef >= 60 else "СРЕДНИЙ"
    strategy = "Trend Following · Kelly-размер позиции"

    print(f"Rendering clip {ticker}...")
    path = await make_clip(ticker, action, entry, tp, sl, wef, verdict, strategy)
    if not path:
        print("FAILED — no candles or render error"); return
    size = os.path.getsize(path) / 1024
    print(f"OK: {path} ({size:.0f} KB)")

    if "--send" in sys.argv:
        ok = await broadcast_clip(ticker, action, entry, tp, sl, wef, verdict, strategy, clip_path=path)
        print(f"VIP send: {ok}")
        if "--free" in sys.argv and settings.telegram_free_channel_id:
            ok2 = await broadcast_clip(ticker, action, entry, tp, sl, wef, verdict, strategy,
                                       chat_id=settings.telegram_free_channel_id, teaser=True,
                                       clip_path=path)
            print(f"Free (teaser) send: {ok2}")


asyncio.run(main())
