"""Send a real signal to WinExtraFlow via webhook.

Usage:
    python scripts/send_signal.py --ticker SBER --action buy --price 315.50 --tp 340 --sl 298
    python scripts/send_signal.py --ticker BTCUSDT --action sell --price 67200 --tp 63000 --sl 69000
    python scripts/send_signal.py --ticker EURUSD --action buy --price 1.0892 --tp 1.0950 --sl 1.0830

Or as one-liner:
    python scripts/send_signal.py SBER buy 315.50 340 298
"""

import argparse
import json
import sys

import httpx


def main():
    parser = argparse.ArgumentParser(description="Send signal to WinExtraFlow")
    parser.add_argument("ticker", nargs="?", help="Ticker (SBER, BTCUSDT, EURUSD)")
    parser.add_argument("action", nargs="?", help="buy or sell")
    parser.add_argument("price", nargs="?", type=float, help="Entry price")
    parser.add_argument("tp", nargs="?", type=float, default=None, help="Take profit")
    parser.add_argument("sl", nargs="?", type=float, default=None, help="Stop loss")
    parser.add_argument("--ticker", dest="ticker_opt")
    parser.add_argument("--action", dest="action_opt")
    parser.add_argument("--price", dest="price_opt", type=float)
    parser.add_argument("--tp", dest="tp_opt", type=float)
    parser.add_argument("--sl", dest="sl_opt", type=float)
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--secret", default="")

    args = parser.parse_args()

    ticker = args.ticker or args.ticker_opt
    action = args.action or args.action_opt
    price = args.price or args.price_opt
    tp = args.tp or args.tp_opt
    sl = args.sl or args.sl_opt

    if not all([ticker, action, price]):
        print("Usage: python send_signal.py SBER buy 315.50 [tp] [sl]")
        sys.exit(1)

    payload = {
        "ticker": ticker.upper(),
        "action": action.lower(),
        "price": price,
        "timeframe": args.timeframe,
    }
    if tp:
        payload["take_profit"] = tp
    if sl:
        payload["stop_loss"] = sl
    if args.secret:
        payload["secret"] = args.secret

    print(f"Sending: {action.upper()} {ticker.upper()} @ {price}")
    if tp:
        print(f"  TP: {tp}")
    if sl:
        print(f"  SL: {sl}")

    resp = httpx.post(f"{args.url}/api/v1/signals/webhook/tradingview", json=payload)

    if resp.status_code == 201:
        data = resp.json()
        print(f"\nSignal created!")
        print(f"  ID: {data.get('id')}")
        print(f"  WEF Score: {data.get('ai_confidence', 'N/A')}")
        print(f"  AI: {data.get('ai_reasoning', '')}")
    else:
        print(f"\nError {resp.status_code}: {resp.text}")


if __name__ == "__main__":
    main()
