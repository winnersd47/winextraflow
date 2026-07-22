"""Run channel discovery across all markets, save results for the UI/API.

Usage:
    python scripts/discover_channels.py            # all markets
    python scripts/discover_channels.py crypto forex
"""

import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.channel_discovery import discover, save_results, MARKET_QUERIES


async def main():
    markets = sys.argv[1:] or list(MARKET_QUERIES.keys())
    print(f"Discovering channels for: {', '.join(markets)}\n")
    results = await discover(markets)

    total = 0
    for market, channels in results.items():
        print(f"\n{'='*58}\n{market.upper()} — {len(channels)} channels\n{'='*58}")
        for c in channels[:12]:
            subs = f"{c['subscribers']//1000}k" if c.get("subscribers") else "?"
            mark = {"signals": "[SIGNALS]", "format_mismatch": "[format?]", "mostly_news": "[news]"}.get(c["tier"], "")
            print(f"  {mark:11} @{c['username']:<24} '{c['title'][:26]}' | {subs} subs | "
                  f"yield={c['yield_pct']}% parsed={c['parsed']}")
            if c.get("sample"):
                print(f"                e.g. {c['sample']}")
        total += len(channels)

    save_results(results)
    print(f"\n{'='*58}")
    print(f"Total: {total} candidate channels saved to discovered_channels.json")

    # Highlight the ready-to-add ones
    ready = []
    for market, channels in results.items():
        for c in channels:
            if c["tier"] == "signals":
                ready.append(c["username"])
    if ready:
        print(f"\nReady to monitor (parseable signals): {', '.join(ready)}")


if __name__ == "__main__":
    asyncio.run(main())
