"""Start MT5 Bridge server — TCP server for MetaTrader 5 connections.

Usage:
    python scripts/mt5_server.py                  # default 127.0.0.1:8765
    python scripts/mt5_server.py --port 8766      # custom port

MT5 sends JSON commands:
    {"cmd": "analyze", "ticker": "EURUSD", "timeframe": "H1", "candles": [...]}
    {"cmd": "batch", "items": [{"ticker": "SBER", "candles": [...]}, ...]}
    {"cmd": "indicators", "candles": [...]}
    {"cmd": "ping"}
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.mt5_bridge import start_mt5_server


def main():
    host = "127.0.0.1"
    port = 8765

    args = sys.argv[1:]
    if "--port" in args:
        idx = args.index("--port")
        port = int(args[idx + 1])
    if "--host" in args:
        idx = args.index("--host")
        host = args[idx + 1]

    # Read what the bridge itself resolved, not os.getenv. A bare os.getenv
    # never sees a value that lives in .env, so this banner used to announce a
    # model nobody had configured and "OpenRouter: NOT SET" while the key was
    # sitting in the file and working. A diagnostic line that lies is worse
    # than no line: the parser outage went unnoticed for fifteen days behind
    # exactly this kind of reassurance.
    from app.services.mt5_bridge import LLM_MODEL, OPENROUTER_KEY

    print(f"MT5 Bridge Server starting on {host}:{port}")
    print(f"LLM Model: {LLM_MODEL}")
    print(f"OpenRouter: {'configured' if OPENROUTER_KEY else 'NOT SET (fallback mode)'}")
    print(f"\nWaiting for MT5 connections...")
    print(f"In MT5: set ServerHost={host}, ServerPort={port}")

    asyncio.run(start_mt5_server(host, port))


if __name__ == "__main__":
    main()
