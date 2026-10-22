"""A scheduled release inside the holding period is stated, not acted on.

The idea came from a channel analysed on 2026-10-16 that argued a trader should
know the week's calendar before entering. It is plausible, and that is the whole
problem: nothing in this project has measured that a rate decision changes a
signal's outcome. The same session refused to gate on "room to target" because
its correlation was only -0.129, and R:R — which sounded obviously right —
measured -0.35 against outcome.

So this warns and never rejects. These tests pin that, and pin the instrument
matching: a Bank of Russia decision has no bearing on AAPL, and saying it does
would be noise dressed as diligence.
"""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import Provider, ProviderSource
from app.models.signal import Signal, SignalAction
from app.services import econ_calendar
from app.services.econ_calendar import _countries_for, events_during_signal


@pytest.fixture
def calendar(monkeypatch):
    """A fixed calendar: one RU and one US release, three days out."""
    soon = (date.today() + timedelta(days=3)).isoformat()
    far = (date.today() + timedelta(days=90)).isoformat()
    events = [
        {"date": soon, "country": "RU", "importance": "high",
         "title": "Заседание ЦБ РФ по ключевой ставке"},
        {"date": soon, "country": "US", "importance": "high",
         "title": "CPI"},
        {"date": soon, "country": "US", "importance": "medium",
         "title": "Housing starts"},
        {"date": far, "country": "RU", "importance": "high",
         "title": "Заседание ЦБ РФ (далёкое)"},
    ]

    async def fake_calendar(days_ahead=30):
        return {"events": events, "count": len(events),
                "sources": ["test"], "notes": []}

    monkeypatch.setattr(econ_calendar, "get_calendar", fake_calendar)
    econ_calendar._cache.clear()
    yield events
    econ_calendar._cache.clear()


# ═══════════════════════════════════════════════════════════════════════
# Which calendar belongs to which instrument
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("ticker,expected", [
    ("SBER", {"RU"}), ("POSI", {"RU"}),
    ("GAZR-12.26", {"RU"}),
    ("AAPL", {"US"}), ("NVDA", {"US"}),
    ("XAUUSD", {"US"}),
    ("USDRUB", {"RU", "US"}),
    ("EURUSD", {"US"}),
    ("BTCUSDT", set()),          # trades through releases; nothing measured
])
def test_market_matching(ticker, expected):
    assert _countries_for(ticker) == expected


@pytest.mark.asyncio
async def test_only_high_importance_events_count(calendar):
    """A medium-importance release is not worth interrupting a reader for."""
    us = await events_during_signal("AAPL")
    titles = {e["title"] for e in us}
    assert "CPI" in titles
    assert "Housing starts" not in titles


@pytest.mark.asyncio
async def test_distant_events_are_outside_the_horizon(calendar):
    ru = await events_during_signal("SBER")
    assert all("далёкое" not in e["title"] for e in ru), ru


@pytest.mark.asyncio
async def test_a_russian_decision_does_not_warn_on_a_us_stock(calendar):
    ru_titles = {e["title"] for e in await events_during_signal("AAPL")}
    assert not any("ЦБ РФ" in t for t in ru_titles), ru_titles


@pytest.mark.asyncio
async def test_crypto_gets_no_event_warning(calendar):
    assert await events_during_signal("BTCUSDT") == []


# ═══════════════════════════════════════════════════════════════════════
# It warns, it does not reject
# ═══════════════════════════════════════════════════════════════════════

async def _signal(db: AsyncSession, ticker="SBER") -> Signal:
    p = Provider(name=f"ev_{uuid.uuid4().hex[:6]}", source=ProviderSource.TELEGRAM)
    db.add(p)
    await db.flush()
    s = Signal(provider_id=p.id, ticker=ticker, action=SignalAction.BUY,
               entry_price=280.0, take_profit=295.0, stop_loss=274.0,
               ai_confidence=0.86, raw_message="x", timeframe="1d")
    db.add(s)
    await db.flush()
    return s


@pytest.mark.asyncio
async def test_event_only_warns(db: AsyncSession, calendar):
    from app.services.signal_quality import check_signal_quality

    s = await _signal(db, "SBER")
    await db.commit()
    r = await check_signal_quality(db, s, None)

    assert r.passed, f"an upcoming release rejected the signal: {r.issues}"
    assert any("публикац" in w for w in r.warnings), r.warnings
    assert not any("публикац" in i for i in r.issues)


@pytest.mark.asyncio
async def test_calendar_outage_does_not_block_a_signal(db: AsyncSession, monkeypatch):
    """Three upstream APIs feed this. None of them may hold up a signal."""
    async def broken(days_ahead=30):
        raise RuntimeError("upstream down")

    monkeypatch.setattr(econ_calendar, "get_calendar", broken)
    econ_calendar._cache.clear()

    from app.services.signal_quality import check_signal_quality
    s = await _signal(db, "SBER")
    await db.commit()
    r = await check_signal_quality(db, s, None)
    assert r.passed, f"a calendar outage blocked a signal: {r.issues}"
    econ_calendar._cache.clear()


@pytest.mark.asyncio
async def test_calendar_is_fetched_once_per_day(calendar, monkeypatch):
    """The gate runs per ingested signal; three APIs each time would be both
    slow and a way to get rate-limited."""
    calls = {"n": 0}
    real = econ_calendar.get_calendar

    async def counting(days_ahead=30):
        calls["n"] += 1
        return await real(days_ahead=days_ahead)

    monkeypatch.setattr(econ_calendar, "get_calendar", counting)
    econ_calendar._cache.clear()

    for _ in range(5):
        await events_during_signal("SBER")
    assert calls["n"] == 1, f"calendar fetched {calls['n']} times"


@pytest.mark.asyncio
async def test_consecutive_days_of_one_event_collapse(monkeypatch):
    """FRED lists one FOMC meeting as four release dates — statement, minutes,
    projections. Reported separately the gate said "19 October (+3 more)",
    which reads as four risks when it is one meeting."""
    start = date.today() + timedelta(days=1)
    events = [{"date": (start + timedelta(days=i)).isoformat(), "country": "US",
               "importance": "high", "title": "Решение FOMC по ставке"}
              for i in range(4)]

    async def fake(days_ahead=30):
        return {"events": events, "count": len(events), "sources": [], "notes": []}

    monkeypatch.setattr(econ_calendar, "get_calendar", fake)
    econ_calendar._cache.clear()

    got = await events_during_signal("AAPL")
    assert len(got) == 1, f"four release dates stayed separate: {got}"
    assert got[0]["days"] == 4
    assert got[0]["date"] == start.isoformat()
    assert got[0]["date_end"] == (start + timedelta(days=3)).isoformat()
    econ_calendar._cache.clear()


@pytest.mark.asyncio
async def test_a_gap_keeps_events_separate(monkeypatch):
    """Two meetings a week apart are two events, not one long one."""
    first = date.today() + timedelta(days=1)
    second = date.today() + timedelta(days=8)
    events = [
        {"date": first.isoformat(), "country": "US", "importance": "high",
         "title": "CPI"},
        {"date": second.isoformat(), "country": "US", "importance": "high",
         "title": "CPI"},
    ]

    async def fake(days_ahead=30):
        return {"events": events, "count": 2, "sources": [], "notes": []}

    monkeypatch.setattr(econ_calendar, "get_calendar", fake)
    econ_calendar._cache.clear()

    got = await events_during_signal("AAPL")
    assert len(got) == 2, f"separate releases were merged: {got}"
    econ_calendar._cache.clear()
