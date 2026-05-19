"""MOEX ISS API Integration — Moscow Exchange real-time data.

Free, no auth required. Base: https://iss.moex.com/iss/
Provides: live quotes, candles, securities info, market indices.

Used for:
1. Live prices for RU stocks (SBER, GAZP, LKOH, YNDX, GMKN)
2. Market overview (indices IMOEX, RTS)
3. Top gainers/losers
4. Candle data for charts
"""

import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

ISS_BASE = "https://iss.moex.com/iss"
BOARD = "TQBR"  # Main board for shares

# Key RU stocks tracked on platform
TRACKED_SECURITIES = ["SBER", "GAZP", "LKOH", "YNDX", "GMKN", "ROSN", "VTBR", "NVTK", "PLZL", "MAGN",
                      "MTSS", "TATN", "SNGS", "ALRS", "NLMK", "MOEX", "POLY", "MGNT", "PHOR", "CHMF"]


class MoexService:
    """Moscow Exchange ISS API client."""

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(base_url=ISS_BASE, timeout=15)

    async def get_live_quotes(self, securities: list[str] | None = None) -> list[dict]:
        """Get real-time quotes for securities from MOEX."""
        tickers = securities or TRACKED_SECURITIES
        sec_list = ",".join(tickers)
        try:
            resp = await self.client.get(
                f"/engines/stock/markets/shares/boards/{BOARD}/securities.json",
                params={
                    "iss.meta": "off",
                    "iss.only": "marketdata,securities",
                    "marketdata.columns": "SECID,LAST,OPEN,HIGH,LOW,VOLTODAY,CHANGE,CHANGEPRCNT,UPDATETIME",
                    "securities.columns": "SECID,SHORTNAME,PREVPRICE",
                    "securities": sec_list,
                },
            )
            data = resp.json()

            md = data.get("marketdata", {})
            sec = data.get("securities", {})
            md_cols = md.get("columns", [])
            sec_cols = sec.get("columns", [])
            md_data = md.get("data", [])
            sec_data = sec.get("data", [])

            # Build name map
            names = {}
            for row in sec_data:
                d = dict(zip(sec_cols, row))
                names[d.get("SECID")] = {"name": d.get("SHORTNAME", ""), "prev_price": d.get("PREVPRICE")}

            quotes = []
            for row in md_data:
                d = dict(zip(md_cols, row))
                secid = d.get("SECID")
                if not secid or d.get("LAST") is None:
                    continue
                info = names.get(secid, {})
                change_pct = d.get("CHANGEPRCNT")
                if change_pct is None and info.get("prev_price") and info["prev_price"] > 0:
                    change_pct = round(((d.get("LAST") or 0) - info["prev_price"]) / info["prev_price"] * 100, 2)
                quotes.append({
                    "ticker": secid,
                    "name": info.get("name", secid),
                    "price": d.get("LAST"),
                    "open": d.get("OPEN"),
                    "high": d.get("HIGH"),
                    "low": d.get("LOW"),
                    "prev_price": info.get("prev_price"),
                    "change": d.get("CHANGE"),
                    "change_pct": change_pct,
                    "volume": d.get("VOLTODAY"),
                    "update_time": d.get("UPDATETIME"),
                })

            return sorted(quotes, key=lambda x: abs(x.get("change_pct") or 0), reverse=True)

        except Exception as e:
            logger.error(f"MOEX quotes error: {e}")
            return []

    async def get_indices(self) -> list[dict]:
        """Get main MOEX indices (IMOEX, RTS, etc)."""
        try:
            resp = await self.client.get(
                "/engines/stock/markets/index/securities.json",
                params={
                    "iss.meta": "off",
                    "iss.only": "marketdata,securities",
                    "marketdata.columns": "SECID,CURRENTVALUE,OPENVALUE,CHANGE,CHANGEPRCNT,UPDATETIME",
                    "securities.columns": "SECID,SHORTNAME",
                },
            )
            data = resp.json()
            md = data.get("marketdata", {})
            sec = data.get("securities", {})
            md_cols = md.get("columns", [])
            sec_cols = sec.get("columns", [])

            names = {}
            for row in sec.get("data", []):
                d = dict(zip(sec_cols, row))
                names[d.get("SECID")] = d.get("SHORTNAME", "")

            indices = []
            target = {"IMOEX", "RTSI", "MOEXBC", "MOEXOG", "MOEXFN", "MOEXTL", "MOEXMM"}
            for row in md.get("data", []):
                d = dict(zip(md_cols, row))
                secid = d.get("SECID")
                if secid not in target or d.get("CURRENTVALUE") is None:
                    continue
                indices.append({
                    "ticker": secid,
                    "name": names.get(secid, secid),
                    "value": d.get("CURRENTVALUE"),
                    "open": d.get("OPENVALUE"),
                    "change": d.get("CHANGE"),
                    "change_pct": d.get("CHANGEPRCNT"),
                    "update_time": d.get("UPDATETIME"),
                })
            return indices

        except Exception as e:
            logger.error(f"MOEX indices error: {e}")
            return []

    async def get_candles(self, ticker: str, interval: int = 60, count: int = 50) -> list[dict]:
        """Get candle data for a security. Interval: 1,10,60 min or 24=daily."""
        try:
            resp = await self.client.get(
                f"/engines/stock/markets/shares/boards/{BOARD}/securities/{ticker}/candles.json",
                params={
                    "iss.meta": "off",
                    "interval": interval,
                    "candles.columns": "open,close,high,low,volume,begin,end",
                    "from": "",  # latest
                    "limit": count,
                },
            )
            data = resp.json()
            cols = data.get("candles", {}).get("columns", [])
            rows = data.get("candles", {}).get("data", [])
            return [dict(zip(cols, row)) for row in rows]

        except Exception as e:
            logger.error(f"MOEX candles error: {e}")
            return []

    async def get_top_movers(self, limit: int = 10) -> dict:
        """Get top gainers and losers on MOEX today."""
        quotes = await self.get_live_quotes(TRACKED_SECURITIES)
        if not quotes:
            return {"gainers": [], "losers": []}

        with_change = [q for q in quotes if q.get("change_pct") is not None]
        sorted_up = sorted(with_change, key=lambda x: x["change_pct"], reverse=True)
        sorted_down = sorted(with_change, key=lambda x: x["change_pct"])

        return {
            "gainers": sorted_up[:limit],
            "losers": sorted_down[:limit],
        }

    async def get_market_overview(self) -> dict:
        """Full MOEX market overview: indices + quotes + top movers."""
        indices = await self.get_indices()
        quotes = await self.get_live_quotes()
        movers = await self.get_top_movers(5)

        return {
            "indices": indices,
            "quotes": quotes,
            "top_gainers": movers["gainers"],
            "top_losers": movers["losers"],
            "total_securities": len(quotes),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


moex_service = MoexService()
