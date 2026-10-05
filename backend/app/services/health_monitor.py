"""External API Health Monitor — checks availability of all data sources.

Monitors:
- MOEX ISS API (quotes, candles, heatmap)
- Binance API (crypto candles)
- Yahoo Finance (forex/stocks candles)
- TradingView (widgets — client-side, checked from frontend)
- YooKassa (payments)
- CryptoCloud (crypto payments)
- Prodamus (international payments)
- Telegram API (channel parsing)

Each source has:
- status: "ok" | "degraded" | "down"
- latency_ms: response time
- last_check: timestamp
- last_error: error message if any
- consecutive_failures: number of failures in a row
"""

import logging
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SourceHealth:
    name: str
    url: str
    status: str = "unknown"  # ok, degraded, down, unknown
    latency_ms: int = 0
    last_check: str = ""
    last_ok: str = ""
    last_error: str = ""
    consecutive_failures: int = 0
    total_checks: int = 0
    total_failures: int = 0


class HealthMonitor:
    """Monitors all external API sources."""

    def __init__(self):
        self.sources: dict[str, SourceHealth] = {
            "moex_iss": SourceHealth(
                name="MOEX ISS API",
                url="https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities.json?iss.meta=off&securities.columns=SECID&limit=1",
            ),
            "binance": SourceHealth(
                name="Binance API",
                url="https://api.binance.com/api/v3/ping",
            ),
            # Second crypto source. Both are monitored on purpose: crypto prices,
            # ATR and candles now fall back between them, so knowing WHICH one is
            # down is the difference between a slowdown and an outage. Binance
            # withdrew from the Russian market, so on the RU VPS this deploys to,
            # Bybit may be the one that answers.
            "bybit": SourceHealth(
                name="Bybit API",
                url="https://api.bybit.com/v5/market/time",
            ),
            "yahoo_finance": SourceHealth(
                name="Yahoo Finance",
                url="https://query1.finance.yahoo.com/v8/finance/chart/AAPL?interval=1d&range=1d",
            ),
            "yookassa": SourceHealth(
                name="YooKassa",
                url="https://api.yookassa.ru/v3/payments?limit=1",
            ),
            "cryptocloud": SourceHealth(
                name="CryptoCloud",
                url="https://api.cryptocloud.plus/v2/invoice/info",
            ),
            "telegram": SourceHealth(
                name="Telegram API",
                url="https://api.telegram.org/bot000000:fake/getMe",
            ),
            "coingecko": SourceHealth(
                name="CoinGecko",
                url="https://api.coingecko.com/api/v3/ping",
            ),
            "fear_greed": SourceHealth(
                name="Fear & Greed Index",
                url="https://api.alternative.me/fng/?limit=1",
            ),
            "cbr": SourceHealth(
                name="CBR Currency Rates",
                url="https://www.cbr-xml-daily.ru/daily_json.js",
            ),
            "defillama": SourceHealth(
                name="DeFi Llama TVL",
                url="https://api.llama.fi/v2/historicalChainTvl",
            ),
        }

    async def check_source(self, key: str) -> SourceHealth:
        """Check a single source."""
        source = self.sources.get(key)
        if not source:
            return SourceHealth(name=key, url="", status="unknown")

        source.total_checks += 1
        start = time.monotonic()
        now = datetime.now(timezone.utc).isoformat()
        source.last_check = now

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                # Special handling per source
                headers = {"User-Agent": "WinExtraFlow/1.0"}

                if key == "yahoo_finance":
                    headers["User-Agent"] = "Mozilla/5.0"
                elif key == "yookassa":
                    if not settings.yookassa_shop_id:
                        source.status = "ok"
                        source.latency_ms = 0
                        source.last_error = "Demo mode (no credentials)"
                        return source
                elif key == "cryptocloud":
                    if not settings.cryptocloud_api_key:
                        source.status = "ok"
                        source.latency_ms = 0
                        source.last_error = "Demo mode (no credentials)"
                        return source
                elif key == "telegram":
                    # Probe the Bot API — that is what the platform actually posts
                    # through. The previous code replaced the URL with a raw
                    # datacenter IP (https://149.154.167.50:443), which can only
                    # fail: a DC speaks MTProto, not HTTP, and presents no
                    # certificate for that address. So this source reported
                    # "degraded" with CERTIFICATE_VERIFY_FAILED at all times, while
                    # posting to both channels worked fine — a permanent false alarm
                    # that also dragged `overall` down and taught the operator to
                    # ignore the status page.
                    #
                    # With a real token, getMe both proves reachability and validates
                    # the token; the two failures need different actions, so they are
                    # reported separately.
                    token = settings.telegram_bot_token
                    if token:
                        source.url = f"https://api.telegram.org/bot{token}/getMe"
                        resp = await client.get(source.url, headers=headers)
                        elapsed = int((time.monotonic() - start) * 1000)
                        source.latency_ms = elapsed
                        # Never store the token in a field the API exposes.
                        source.url = "https://api.telegram.org/bot<token>/getMe"
                        if resp.status_code == 200:
                            source.status = "ok" if elapsed < 3000 else "degraded"
                            source.consecutive_failures = 0
                            source.last_ok = now
                            source.last_error = ""
                        elif resp.status_code in (401, 403):
                            # Reachable but the token is rejected — posting will fail.
                            source.consecutive_failures += 1
                            source.total_failures += 1
                            source.status = "degraded"
                            source.last_error = ("Bot token rejected "
                                                 f"(HTTP {resp.status_code}) — reissue it")
                        else:
                            source.consecutive_failures += 1
                            source.total_failures += 1
                            source.status = ("degraded" if source.consecutive_failures < 3
                                             else "down")
                            source.last_error = f"HTTP {resp.status_code}"
                        return source
                    # No bot token: a fake one still proves the API answers (401).
                    source.url = "https://api.telegram.org/bot000000:fake/getMe"

                resp = await client.get(source.url, headers=headers)
                elapsed = int((time.monotonic() - start) * 1000)
                source.latency_ms = elapsed

                # Consider 2xx and some 4xx as "reachable"
                if resp.status_code < 500:
                    source.status = "ok" if elapsed < 3000 else "degraded"
                    source.consecutive_failures = 0
                    source.last_ok = now
                    source.last_error = ""
                else:
                    source.consecutive_failures += 1
                    source.total_failures += 1
                    source.status = "degraded" if source.consecutive_failures < 3 else "down"
                    source.last_error = f"HTTP {resp.status_code}"

        except httpx.TimeoutException:
            elapsed = int((time.monotonic() - start) * 1000)
            source.latency_ms = elapsed
            source.consecutive_failures += 1
            source.total_failures += 1
            source.status = "degraded" if source.consecutive_failures < 3 else "down"
            source.last_error = "Timeout"

        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            source.latency_ms = elapsed
            source.consecutive_failures += 1
            source.total_failures += 1
            source.status = "degraded" if source.consecutive_failures < 3 else "down"
            source.last_error = str(e)[:200]

        if source.status == "down":
            logger.warning(f"HEALTH: {source.name} is DOWN ({source.consecutive_failures} failures). Last error: {source.last_error}")

        return source

    async def check_all(self) -> dict:
        """Check all sources and return full report."""
        results = {}
        for key in self.sources:
            results[key] = await self.check_source(key)

        # Summary
        all_statuses = [s.status for s in results.values()]
        down_count = sum(1 for s in all_statuses if s == "down")
        degraded_count = sum(1 for s in all_statuses if s == "degraded")

        if down_count > 0:
            overall = "critical"
        elif degraded_count > 0:
            overall = "degraded"
        else:
            overall = "healthy"

        return {
            "overall": overall,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "total_sources": len(results),
            "down": down_count,
            "degraded": degraded_count,
            "healthy": len(results) - down_count - degraded_count,
            "sources": {
                key: {
                    "name": s.name,
                    "status": s.status,
                    "latency_ms": s.latency_ms,
                    "last_check": s.last_check,
                    "last_ok": s.last_ok,
                    "last_error": s.last_error,
                    "consecutive_failures": s.consecutive_failures,
                    "uptime_pct": round((1 - s.total_failures / max(s.total_checks, 1)) * 100, 1),
                }
                for key, s in results.items()
            },
            "alerts": [
                {
                    "source": s.name,
                    "status": s.status,
                    "error": s.last_error,
                    "failures": s.consecutive_failures,
                }
                for s in results.values()
                if s.status in ("down", "degraded")
            ],
        }

    def get_cached_state(self) -> dict:
        """Get last known state without re-checking."""
        return {
            key: {
                "name": s.name,
                "status": s.status,
                "latency_ms": s.latency_ms,
                "last_check": s.last_check,
                "last_error": s.last_error,
            }
            for key, s in self.sources.items()
        }


health_monitor = HealthMonitor()
