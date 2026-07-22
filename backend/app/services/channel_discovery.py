"""Channel discovery — search Telegram for signal channels across all markets.

Uses the phone session (Telethon global search) to find public channels by
market keywords, then scores each by signal-parse yield. Results feed the
project's messenger UI (search + add-to-monitoring).

Markets: MOEX (RU stocks), Crypto, Forex, US Stocks, Commodities.
"""

import asyncio
import json
import logging
import os

from telethon import TelegramClient
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.types import Channel

from app.config import settings
from app.services.telegram import telegram_parser

logger = logging.getLogger(__name__)

# Market -> search queries (RU + EN)
MARKET_QUERIES = {
    "moex": ["инвест идеи", "сигналы акции", "трейдинг мосбиржа", "российские акции", "фондовый рынок"],
    "crypto": ["crypto signals", "bitcoin signals", "крипто сигналы", "crypto trading", "altcoin signals"],
    "forex": ["forex signals", "форекс сигналы", "forex trading", "fx signals"],
    "stocks_us": ["stock signals", "us stocks ideas", "trading ideas stocks", "wall street signals"],
    "commodities": ["gold signals", "oil trading signals", "золото нефть сигналы", "commodity trading"],
}

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                         "discovered_channels.json")


def _proxy():
    if settings.socks5_host and settings.socks5_port:
        import socks
        return (socks.SOCKS5, settings.socks5_host, int(settings.socks5_port), True,
                settings.socks5_user or None, settings.socks5_pass or None)
    return None


async def _score_channel(client: TelegramClient, entity) -> dict | None:
    """Fetch recent messages, compute signal-parse yield for a channel."""
    username = getattr(entity, "username", None)
    if not username:
        return None  # need public username to monitor
    try:
        msgs = await client.get_messages(entity, limit=20)
    except Exception:
        return None

    siglike = parsed = 0
    sample = ""
    for m in msgs:
        if not m.text:
            continue
        if telegram_parser.is_signal_message(m.text):
            siglike += 1
            p = telegram_parser.parse_message(m.text)
            if p:
                parsed += 1
                if not sample:
                    tp = f" TP:{p.take_profit}" if p.take_profit else ""
                    sample = f"{p.action.upper()} {p.ticker} @ {p.entry_price}{tp}"

    if siglike == 0:
        return None  # not a signal/trading channel at all

    total = len([m for m in msgs if m.text])
    yield_pct = round(parsed / total * 100) if total else 0
    if parsed > 0:
        tier = "signals"
    elif siglike >= 5:
        tier = "format_mismatch"  # posts signals, parser needs work
    else:
        tier = "mostly_news"

    return {
        "username": username,
        "title": getattr(entity, "title", username),
        "subscribers": getattr(entity, "participants_count", None),
        "signal_like": siglike,
        "parsed": parsed,
        "yield_pct": yield_pct,
        "tier": tier,
        "sample": sample,
    }


async def discover(markets: list[str] | None = None, client: TelegramClient | None = None,
                   per_query_limit: int = 20) -> dict:
    """Search all (or given) markets, return ranked channels per market.

    If client is None, opens a session copy (safe against locks).
    """
    markets = markets or list(MARKET_QUERIES.keys())
    own_client = client is None
    if own_client:
        import shutil
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        src = os.path.join(base, "winextraflow_bot.session")
        work = os.path.join(base, "wef_discover.session")
        if os.path.exists(src):
            shutil.copyfile(src, work)
        client = TelegramClient(work, int(settings.telegram_api_id),
                                settings.telegram_api_hash, proxy=_proxy())
        await client.connect()

    results: dict[str, list] = {}
    seen_globally = set()
    try:
        for market in markets:
            queries = MARKET_QUERIES.get(market, [])
            found: dict[str, dict] = {}
            for q in queries:
                try:
                    res = await client(SearchRequest(q=q, limit=per_query_limit))
                except Exception as e:
                    logger.warning(f"Search '{q}' failed: {e}")
                    continue
                for ch in res.chats:
                    if not isinstance(ch, Channel):
                        continue
                    uname = getattr(ch, "username", None)
                    if not uname or uname in found or uname in seen_globally:
                        continue
                    scored = await _score_channel(client, ch)
                    if scored:
                        found[uname] = scored
                        seen_globally.add(uname)
                    await asyncio.sleep(0.2)
            # Rank: signals-tier first, then by parsed count, then signal_like
            ranked = sorted(found.values(),
                            key=lambda c: (c["tier"] == "signals", c["parsed"], c["signal_like"]),
                            reverse=True)
            results[market] = ranked
            logger.info(f"Market {market}: {len(ranked)} candidate channels")
    finally:
        if own_client:
            await client.disconnect()

    return results


def save_results(results: dict):
    payload = {"markets": results}
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_results() -> dict:
    if not os.path.exists(DATA_FILE):
        return {"markets": {}}
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"markets": {}}


# ─── Monitored channels (parse list) — persisted, read by worker/backfill ───

MONITORED_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                              "monitored_channels.json")


def load_monitored() -> list[str]:
    """Channels currently monitored for parsing. Seeds from .env on first run."""
    if os.path.exists(MONITORED_FILE):
        try:
            with open(MONITORED_FILE, encoding="utf-8") as f:
                return json.load(f).get("channels", [])
        except Exception:
            pass
    # Seed from .env TELEGRAM_PARSE_CHANNELS
    return [c.strip() for c in settings.telegram_parse_channels.split(",") if c.strip()]


def save_monitored(channels: list[str]):
    # dedupe, keep order
    seen, out = set(), []
    for c in channels:
        c = c.strip().lstrip("@")
        if c and c.lower() not in seen:
            seen.add(c.lower())
            out.append(c)
    with open(MONITORED_FILE, "w", encoding="utf-8") as f:
        json.dump({"channels": out}, f, ensure_ascii=False, indent=2)
    return out


def add_monitored(username: str) -> list[str]:
    chans = load_monitored()
    chans.append(username)
    return save_monitored(chans)


def remove_monitored(username: str) -> list[str]:
    u = username.strip().lstrip("@").lower()
    chans = [c for c in load_monitored() if c.lower() != u]
    return save_monitored(chans)
