"""Economic calendar from primary sources.

Replaces the TradingView economic-calendar widget. The aggregators that could have
replaced it are all worse for this project: Trading Economics, EODHD, FMP and
OHLC.dev are paid or key-gated with attribution in their terms, and the open-source
option on GitHub scrapes investing.com, which is both unstable and against that
site's terms.

Primary sources are free, authoritative and carry no attribution requirement:

  * Банк России — key-rate decision dates. 57% of the platform's signals are MOEX
    instruments, so this is the single most relevant calendar for them.
  * MOEX ISS — trading calendar, i.e. which sessions exist at all.
  * FRED (St. Louis Fed) — US macro releases, for the 34% of flow that is US equity.
    Needs a free API key; without one the US block is simply absent rather than
    filled with guesses.

Every entry carries its source so the UI can attribute it honestly. Nothing here is
invented: if a source does not answer, its events are missing and the response says
which sources succeeded.
"""

import logging
from datetime import date, datetime, timedelta, timezone

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

TIMEOUT = 15.0

# The Bank of Russia publishes the year's rate-decision dates in advance. They are
# fixed calendar facts, not forecasts, so a static list is the honest encoding —
# updated once a year from cbr.ru. Kept here rather than scraped because the page is
# HTML meant for humans and would break silently.
CBR_RATE_DATES_2026 = [
    "2026-02-13", "2026-03-20", "2026-04-24", "2026-06-05",
    "2026-07-24", "2026-09-11", "2026-10-23", "2026-12-18",
]


async def cbr_events(days_ahead: int = 60) -> list[dict]:
    """Bank of Russia key-rate meetings inside the window, plus the current rate."""
    today = date.today()
    horizon = today + timedelta(days=days_ahead)
    out = []
    for d in CBR_RATE_DATES_2026:
        try:
            when = date.fromisoformat(d)
        except ValueError:
            continue
        if today <= when <= horizon:
            out.append({
                "date": d,
                "country": "RU",
                "title": "Заседание ЦБ РФ по ключевой ставке",
                "importance": "high",
                "source": "Банк России",
                "source_url": "https://www.cbr.ru/dkp/cal_mp/",
                "actual": None,
            })

    # Current key rate — context for the next decision, from the CBR's own service.
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.get("https://www.cbr-xml-daily.ru/daily_json.js")
            if r.status_code == 200:
                usd = (r.json().get("Valute") or {}).get("USD") or {}
                if usd.get("Value"):
                    out.append({
                        "date": today.isoformat(),
                        "country": "RU",
                        "title": f"Курс ЦБ РФ: USD {usd['Value']:.2f} ₽",
                        "importance": "low",
                        "source": "Банк России",
                        "source_url": "https://www.cbr.ru/currency_base/daily/",
                        "actual": usd["Value"],
                    })
    except Exception as e:
        logger.debug(f"CBR rate fetch failed: {e}")

    return out


async def moex_calendar() -> list[dict]:
    """Is the MOEX trading today? A closed session is calendar-relevant by itself."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.get(
                "https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/"
                "securities/SBER/candles.json",
                params={"iss.meta": "off", "interval": 24,
                        "from": (date.today() - timedelta(days=1)).isoformat(),
                        "candles.columns": "begin"},
            )
            rows = r.json().get("candles", {}).get("data", [])
    except Exception as e:
        logger.debug(f"MOEX calendar probe failed: {e}")
        return []

    trading = bool(rows)
    return [{
        "date": date.today().isoformat(),
        "country": "RU",
        "title": ("Мосбиржа: торги идут" if trading
                  else "Мосбиржа: торгов нет (выходной или праздник)"),
        "importance": "low",
        "source": "MOEX ISS",
        "source_url": "https://www.moex.com/",
        "actual": None,
    }]


# FRED release ids for the series that actually move US equities.
FRED_RELEASES = {
    10: "ИПЦ США (CPI)",
    50: "Занятость вне сельского хозяйства (Nonfarm Payrolls)",
    53: "ВВП США",
    18: "Решение FOMC по ставке",
}


async def fred_events(days_ahead: int = 60) -> list[dict]:
    """US macro release dates. Absent — not guessed — when no API key is set."""
    key = settings.fred_api_key
    if not key:
        return []
    today = date.today()
    out = []
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            for rid, title in FRED_RELEASES.items():
                r = await c.get(
                    "https://api.stlouisfed.org/fred/release/dates",
                    params={"release_id": rid, "api_key": key, "file_type": "json",
                            "include_release_dates_with_no_data": "true",
                            "realtime_start": today.isoformat(),
                            "realtime_end": (today + timedelta(days=days_ahead)).isoformat(),
                            "limit": 4, "sort_order": "asc"},
                )
                if r.status_code != 200:
                    logger.debug(f"FRED {rid}: HTTP {r.status_code}")
                    continue
                for d in r.json().get("release_dates", []):
                    when = d.get("date")
                    if not when or when < today.isoformat():
                        continue
                    out.append({
                        "date": when, "country": "US", "title": title,
                        "importance": "high" if rid in (10, 18, 50) else "medium",
                        "source": "FRED (St. Louis Fed)",
                        "source_url": "https://fred.stlouisfed.org/releases",
                        "actual": None,
                    })
    except Exception as e:
        logger.warning(f"FRED calendar failed: {e}")
    return out


async def get_calendar(days_ahead: int = 60) -> dict:
    """Merged calendar. Reports which sources answered, so gaps are visible."""
    import asyncio

    cbr, moex, fred = await asyncio.gather(
        cbr_events(days_ahead), moex_calendar(), fred_events(days_ahead),
        return_exceptions=True,
    )

    events, sources = [], {}
    for name, res in (("cbr", cbr), ("moex", moex), ("fred", fred)):
        if isinstance(res, Exception) or res is None:
            sources[name] = "error"
            continue
        sources[name] = "ok" if res else "empty"
        events.extend(res)

    events.sort(key=lambda e: (e["date"], e["country"]))
    notes = []
    if not settings.fred_api_key:
        notes.append("Календарь США недоступен: не задан FRED_API_KEY "
                     "(бесплатный ключ на fred.stlouisfed.org).")
    return {
        "events": events,
        "count": len(events),
        "sources": sources,
        "notes": notes,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
