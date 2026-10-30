"""Candle windows must come back whole, or not come back pretending to be whole.

Every one of the three crypto exchanges caps a kline response and says nothing
when the window needed more. A backtest then runs on a slice of the period it
asked for, and nothing in the output says which slice:

  * MEXC caps at 500 and ignores a larger `limit` outright. A 120-day 4h run
    (720 bars) measured 2 July to 23 September and never saw the last five
    weeks — found because the dates printed by paper_advisors.py ended a month
    before the day it was run;
  * Binance caps at 1000. Two months of 15m bars is 5 700; it returned the
    oldest 1 000;
  * Bybit caps at 1000 AND effectively ignores `start` when the range is
    bigger, returning the NEWEST page instead. So it has to be paged backwards
    — paging it forward like the other two makes no progress at all, which the
    first attempt here did.

These are stubbed. Live calls belong in a one-off check, not in a suite that
has to pass on a train.
"""
import httpx
import pytest

from app.services import backtesting_real as bt

DAY_MS = 24 * 60 * 60 * 1000
START_MS = 1_767_225_600_000   # 2026-01-01


def _kline(ts):
    return [ts, "100", "101", "99", "100.5", "10", ts + DAY_MS, "1000"]


def _bybit_row(ts):
    return [str(ts), "100", "101", "99", "100.5", "10", "1000"]


class _Resp:
    def __init__(self, payload):
        self._p, self.status_code = payload, 200
        self.text = str(payload)

    def json(self):
        return self._p


def _paging_stub(monkeypatch, total: int, page: int, *, bybit=False,
                 newest_first=False, calls=None):
    """An exchange holding `total` daily bars that answers `page` at a time."""
    bars = [START_MS + i * DAY_MS for i in range(total)]

    async def _get(_self, _url, params=None, **k):
        params = params or {}
        if calls is not None:
            calls.append(dict(params))
        lo = int(params.get("startTime") or params.get("start") or 0)
        hi = int(params.get("endTime") or params.get("end") or 10 ** 15)
        window = [b for b in bars if lo <= b <= hi]
        chunk = window[-page:] if newest_first else window[:page]
        if bybit:
            rows = [_bybit_row(b) for b in reversed(chunk)]
            return _Resp({"retCode": 0, "result": {"list": rows}})
        return _Resp([_kline(b) for b in chunk])

    monkeypatch.setattr(httpx.AsyncClient, "get", _get)
    return bars


@pytest.mark.asyncio
async def test_mexc_pages_past_its_cap(monkeypatch):
    _paging_stub(monkeypatch, total=1250, page=bt.MEXC_PAGE)
    got = await bt.fetch_mexc_candles("BTCUSDT", "2026-01-01", "2030-01-01")
    assert len(got) == 1250, "страницы после первой потеряны"


@pytest.mark.asyncio
async def test_binance_pages_past_its_cap(monkeypatch):
    # 2500 daily bars run past 2030, so the window has to be wider than the
    # data or the stub clips it and the test measures its own fixture.
    _paging_stub(monkeypatch, total=2500, page=bt.BINANCE_PAGE)
    got = await bt.fetch_binance_candles("BTCUSDT", "2026-01-01", "2036-01-01")
    assert len(got) == 2500


@pytest.mark.asyncio
async def test_bybit_pages_backwards(monkeypatch):
    """It returns the newest page, so only pulling `end` earlier gets anywhere."""
    calls = []
    _paging_stub(monkeypatch, total=2500, page=bt.BYBIT_PAGE,
                 bybit=True, newest_first=True, calls=calls)
    got = await bt.fetch_bybit_candles("BTCUSDT", "2026-01-01", "2036-01-01")

    assert len(got) == 2500
    ends = [int(c["end"]) for c in calls]
    assert ends == sorted(ends, reverse=True) and len(set(ends)) > 1, \
        "окно не двигалось назад — листание вперёд у Bybit не работает"


@pytest.mark.asyncio
async def test_results_are_oldest_first_and_unique(monkeypatch):
    for fetch, kw in ((bt.fetch_mexc_candles, {}),
                      (bt.fetch_binance_candles, {}),
                      (bt.fetch_bybit_candles, {"bybit": True,
                                                "newest_first": True})):
        _paging_stub(monkeypatch, total=1500, page=1000, **kw)
        got = await fetch("BTCUSDT", "2026-01-01", "2036-01-01")
        stamps = [c["begin"] for c in got]
        assert stamps == sorted(stamps), f"{fetch.__name__}: порядок не по возрастанию"
        assert len(stamps) == len(set(stamps)), f"{fetch.__name__}: дубли на стыке страниц"


@pytest.mark.asyncio
async def test_an_exchange_repeating_itself_does_not_loop_forever(monkeypatch):
    """No forward progress must end the loop, not spin MEXC_MAX_PAGES times."""
    calls = []

    async def _stuck(_self, _url, params=None, **k):
        calls.append(1)
        return _Resp([_kline(START_MS)] * bt.MEXC_PAGE)

    monkeypatch.setattr(httpx.AsyncClient, "get", _stuck)
    got = await bt.fetch_mexc_candles("BTCUSDT", "2026-01-01", "2030-01-01")
    assert len(got) == 1          # all duplicates collapse
    assert len(calls) <= 2


@pytest.mark.asyncio
async def test_a_rejected_symbol_still_returns_empty(monkeypatch):
    async def _reject(_self, _url, params=None, **k):
        return _Resp({"code": -1121, "msg": "Invalid symbol."})

    monkeypatch.setattr(httpx.AsyncClient, "get", _reject)
    assert await bt.fetch_mexc_candles("NOPE", "2026-01-01", "2026-02-01") == []
    assert await bt.fetch_binance_candles("NOPE", "2026-01-01", "2026-02-01") == []


# ── MEXC speaks a different interval vocabulary ────────────────────────────

@pytest.mark.asyncio
async def test_binance_hour_is_translated_for_mexc(monkeypatch):
    """`1h` is "Invalid interval." at MEXC; callers across this project pass it."""
    calls = []
    _paging_stub(monkeypatch, total=10, page=500, calls=calls)
    await bt.fetch_mexc_candles("BTCUSDT", "2026-01-01", "2026-02-01", "1h")
    assert calls and calls[0]["interval"] == "60m"


@pytest.mark.asyncio
async def test_an_interval_mexc_lacks_returns_nothing(monkeypatch):
    """So fetch_crypto_candles moves on instead of calling the symbol empty."""
    called = []

    async def _get(_self, *a, **k):
        called.append(1)
        return _Resp([])

    monkeypatch.setattr(httpx.AsyncClient, "get", _get)
    assert await bt.fetch_mexc_candles("BTCUSDT", "2026-01-01", "2026-02-01", "2h") == []
    assert not called, "запрос вообще не должен уходить"


def test_the_interval_map_covers_what_callers_use():
    for iv in ("1m", "5m", "15m", "30m", "1h", "4h", "1d"):
        assert iv in bt._MEXC_INTERVALS, iv
    assert bt._MEXC_INTERVALS["1h"] == "60m"
    assert bt._MEXC_INTERVALS["1w"] == "1W"
