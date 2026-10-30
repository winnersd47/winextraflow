"""MEXC as the third crypto source for quotes and candles.

Crypto hung off Binance, then off Binance and Bybit. Binance withdrew from the
Russian market and the RU VPS this deploys to may see restrictions the
developer's network does not — and a crypto signal with no price source gets no
monitoring, no ATR and no chart. MEXC was measured answering that network
directly (2026-10-29: ping and quotes 200 in ~0.5-1.1s, no proxy).

The trap this file exists for: MEXC returns `priceChangePercent` as a FRACTION
(-0.0334 for -3.34%) where Binance returns a percentage in the same field. Read
unscaled, every move is understated 100x — and the card would print -0.03% for
a -3.3% day. Bybit has the identical quirk, which is why it is worth a test
rather than a comment.

No network: every test here stubs the HTTP client, because live prices made
this suite flaky once already.
"""
import json

import httpx
import pytest

from app.services import backtesting_real as bt
from app.services import live_price as lp

# One real BTCUSDT response, trimmed. -3.34% on the day.
MEXC_24H = {
    "symbol": "BTCUSDT", "lastPrice": "77417.94", "openPrice": "80099.25",
    "highPrice": "81941.15", "lowPrice": "76527.02", "volume": "9055.76547096",
    "priceChange": "-2681.31", "priceChangePercent": "-0.0334",
}
# A real row: eight elements, not Binance's twelve.
MEXC_KLINE = [1793232000000, "81341.51", "81941.15", "77930", "77994.19",
              "6268.03190218", 1793318400000, "501806503.48"]

MEXC_ERROR = {"msg": "invalid symbol", "code": -1121}


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    @property
    def text(self):
        return json.dumps(self._payload)

    def json(self):
        return self._payload


def _stub(monkeypatch, payload, status=200):
    """Replace httpx.AsyncClient so nothing leaves the machine."""
    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            return _Resp(payload, status)

    monkeypatch.setattr(httpx, "AsyncClient", _Client)


@pytest.mark.asyncio
async def test_change_pct_is_scaled_from_a_fraction(monkeypatch):
    """-0.0334 in the field means -3.34% on the card."""
    _stub(monkeypatch, MEXC_24H)
    quote = await lp._mexc_price("BTCUSDT")

    assert quote["change_pct"] == pytest.approx(-3.34, abs=0.01), (
        "priceChangePercent у MEXC — доля, а не проценты; без ×100 "
        "движение занижается в 100 раз"
    )
    # Cross-check against the prices in the same response.
    implied = (float(MEXC_24H["lastPrice"]) - float(MEXC_24H["openPrice"])) \
        / float(MEXC_24H["openPrice"]) * 100
    assert quote["change_pct"] == pytest.approx(implied, abs=0.05)


@pytest.mark.asyncio
async def test_quote_carries_the_fields_a_card_needs(monkeypatch):
    _stub(monkeypatch, MEXC_24H)
    q = await lp._mexc_price("BTCUSDT")
    assert q["source"] == "MEXC"
    assert q["price"] == pytest.approx(77417.94)
    assert q["high"] > q["low"] > 0
    assert q["open"] > 0 and q["volume"] > 0
    assert q["ticker"] == "BTCUSDT"


@pytest.mark.asyncio
async def test_unknown_symbol_is_none_not_a_crash(monkeypatch):
    """MEXC answers 400 with a dict, which must not be read as a quote."""
    _stub(monkeypatch, MEXC_ERROR, status=400)
    assert await lp._mexc_price("NOPE123") is None


@pytest.mark.asyncio
async def test_zero_price_is_rejected(monkeypatch):
    _stub(monkeypatch, {**MEXC_24H, "lastPrice": "0"})
    assert await lp._mexc_price("BTCUSDT") is None


@pytest.mark.asyncio
async def test_candles_parse_from_an_eight_element_row(monkeypatch):
    # Distinct timestamps: two identical rows are one bar sent twice, and the
    # pager now collapses those — a page boundary repeats its edge.
    later = [MEXC_KLINE[0] + 86_400_000] + MEXC_KLINE[1:]
    _stub(monkeypatch, [MEXC_KLINE, later])
    candles = await bt.fetch_mexc_candles("BTCUSDT", "2026-10-20", "2026-10-29")

    assert len(candles) == 2
    c = candles[0]
    assert c["open"] == pytest.approx(81341.51)
    assert c["high"] == pytest.approx(81941.15)
    assert c["low"] == pytest.approx(77930.0)
    assert c["close"] == pytest.approx(77994.19)
    assert c["high"] >= c["open"] >= c["low"]
    assert c["begin"].startswith("2026-")


@pytest.mark.asyncio
async def test_error_body_is_not_parsed_as_candles(monkeypatch):
    """A dict iterated as rows is where "could not convert string to float"
    came from on the Binance path."""
    _stub(monkeypatch, MEXC_ERROR, status=400)
    assert await bt.fetch_mexc_candles("NOPE123", "2026-10-20", "2026-10-29") == []


@pytest.mark.asyncio
async def test_a_short_row_is_skipped_not_fatal(monkeypatch):
    _stub(monkeypatch, [MEXC_KLINE, [1793232000000, "1", "2"]])
    assert len(await bt.fetch_mexc_candles("BTCUSDT", "2026-10-20", "2026-10-29")) == 1


def test_every_source_is_in_the_chain():
    assert set(lp.CRYPTO_SOURCE_NAMES) == {"binance", "bybit", "mexc"}


def test_sources_resolve_at_call_time(monkeypatch):
    """A dict built at import would keep calling the real exchange.

    The fallback is tested by replacing a source on the module; if the registry
    captured the function objects, that patch would be silently ignored and the
    test would hit the network instead of the stub.
    """
    async def _fake(_t):
        return {"ticker": _t, "price": 1.0, "source": "fake"}

    monkeypatch.setattr(lp, "_binance_price", _fake)
    assert lp._crypto_sources()["binance"] is _fake


@pytest.mark.parametrize("primary", ["binance", "bybit", "mexc"])
def test_primary_goes_first_and_nothing_is_dropped(monkeypatch, primary):
    """Setting CRYPTO_PRIMARY must reorder, never shorten, the chain."""
    monkeypatch.setattr(lp, "CRYPTO_PRIMARY", primary)
    sources = lp._crypto_sources()
    order = lp._crypto_order(sources)

    assert order[0] is sources[primary]
    assert len(order) == len(sources)
    assert len(set(order)) == len(order), "источник попал в цепочку дважды"


def test_an_unknown_primary_still_tries_everything(monkeypatch):
    """A typo in the env var must not silently disable crypto pricing."""
    monkeypatch.setattr(lp, "CRYPTO_PRIMARY", "binace")
    sources = lp._crypto_sources()
    assert len(lp._crypto_order(sources)) == len(sources)


@pytest.mark.asyncio
async def test_quotes_and_candles_share_one_precedence(monkeypatch):
    """A card's price and its chart must not come from differently ranked
    exchanges — the chart would contradict the number printed above it."""
    monkeypatch.setattr(lp, "CRYPTO_PRIMARY", "mexc")

    calls = []

    async def _spy(name):
        async def _f(*a, **k):
            calls.append(name)
            return []
        return _f

    monkeypatch.setattr(bt, "fetch_binance_candles", await _spy("binance"))
    monkeypatch.setattr(bt, "fetch_bybit_candles", await _spy("bybit"))
    monkeypatch.setattr(bt, "fetch_mexc_candles", await _spy("mexc"))

    await bt.fetch_crypto_candles("BTCUSDT", "2026-10-20", "2026-10-29")
    assert calls[0] == "mexc"
    assert set(calls) == {"binance", "bybit", "mexc"}


@pytest.mark.asyncio
async def test_end_of_range_day_is_requested(monkeypatch):
    """MEXC's endTime is exclusive where Binance's is inclusive.

    Asking both for 25-29 October returned five candles from Binance and four
    from MEXC: the 29th was missing. Same backtest, different answer depending
    on which exchange replied — and the dropped bar is the newest one, the one
    an ATR weighs most.
    """
    seen = {}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, _url, params=None, **k):
            seen.update(params or {})
            return _Resp([MEXC_KLINE])

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    await bt.fetch_mexc_candles("BTCUSDT", "2026-10-25", "2026-10-29")

    day_ms = 24 * 60 * 60 * 1000
    span = seen["endTime"] - seen["startTime"]
    assert span == 5 * day_ms - 1, (
        "окно должно покрывать весь последний день — иначе свеча за date_to "
        f"теряется (получено {span / day_ms:.2f} суток)"
    )
