"""Every ticker the pipeline accepts must reach a price source that knows it.

`get_live_price` used to route on a 24-entry `MOEX_TICKERS` literal while
`asset_class` — which consults `detect_source` and knows about sixty names —
was already right. POSI, ASTR, WUSH, SVCB, SIBN, YDEX and others were therefore
sent to Yahoo, which does not list them, and MOEX futures had no branch at all.

The consequence was not a log line. Without a live price the pipeline falls back
to a computed entry, which is the fabricated-level problem this project spent
months unwinding; `stale_tolerance` has nothing to compare against; and the
monitor can never resolve the signal, so it expires unreached. 15 of 161 real
signals — 9% — were in that state when this was found.

These tests are offline: routing is asserted by patching the fetchers, so a
market being shut or a source being unreachable cannot make them fail.
"""

import pytest

from app.services import live_price
from app.services.live_price import asset_class


# Tickers that actually appeared in stored signals, by the class they belong to.
CASES = [
    # MOEX names that were missing from the old literal
    ("POSI", "moex"), ("ASTR", "moex"), ("WUSH", "moex"), ("SVCB", "moex"),
    ("SIBN", "moex"), ("YDEX", "moex"), ("IRAO", "moex"), ("RTKM", "moex"),
    ("BANE", "moex"), ("SNGSP", "moex"),
    # ...and ones that were present, which must keep working
    ("SBER", "moex"), ("GAZP", "moex"), ("LKOH", "moex"),
    # FORTS futures, which had no branch at all
    ("GAZR-12.26", "futures"), ("RTS-12.26", "futures"),
    ("BR-11.26", "futures"), ("VTBR-12.26", "futures"),
    # unchanged classes
    ("BTCUSDT", "crypto"), ("ETHUSDT", "crypto"),
    ("AAPL", "stocks"), ("NVDA", "stocks"),
    ("EURUSD", "forex"), ("GBPJPY", "forex"),
    # Metals read like FX pairs but neither half is a currency, so they
    # landed in "stocks" and inherited its 7% staleness tolerance.
    ("XAUUSD", "commodity"), ("XBRUSD", "commodity"),
]


@pytest.fixture
def routed(monkeypatch):
    """Record which fetcher `get_live_price` picked, without network access."""
    seen = {}

    def stub(name):
        async def fake(ticker):
            seen["dest"] = name
            seen["ticker"] = ticker
            return {"ticker": ticker, "price": 1.0, "source": name}
        return fake

    monkeypatch.setattr(live_price, "_moex_price", stub("moex"))
    monkeypatch.setattr(live_price, "_crypto_price", stub("crypto"))
    monkeypatch.setattr(live_price, "_yahoo_price", stub("yahoo"))
    monkeypatch.setattr(live_price, "_moex_futures_price", stub("futures"))
    return seen


@pytest.mark.asyncio
@pytest.mark.parametrize("ticker,expected_class", CASES)
async def test_every_ticker_reaches_a_source_that_knows_it(ticker, expected_class,
                                                           routed):
    assert asset_class(ticker) == expected_class, \
        f"{ticker} is classified as {asset_class(ticker)}"

    result = await live_price.get_live_price(ticker)
    assert result is not None, f"{ticker} produced no quote at all"

    want = {"moex": "moex", "futures": "futures", "crypto": "crypto",
            "stocks": "yahoo", "forex": "yahoo", "commodity": "yahoo"}[expected_class]
    assert routed["dest"] == want, (
        f"{ticker} ({expected_class}) was routed to {routed['dest']}, "
        f"which does not list it")


@pytest.mark.asyncio
async def test_routing_follows_asset_class_not_a_literal_set(routed):
    """A hardcoded set will always lag behind the tickers being ingested.

    POSI is the proof: present in `detect_source`, absent from `MOEX_TICKERS`,
    and silently broken for as long as both existed.
    """
    import ast
    import inspect
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "app" / "services"
           / "live_price.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.parse(src).body
              if isinstance(n, ast.AsyncFunctionDef) and n.name == "get_live_price")

    # Compare the executable statements only. Comments and the docstring both
    # mention MOEX_TICKERS to explain what went wrong, and a test that reads its
    # own explanation has caught nothing — this project has made that mistake
    # twice before.
    stmts = fn.body[1:] if (fn.body and isinstance(fn.body[0], ast.Expr)
                            and isinstance(fn.body[0].value, ast.Constant)
                            and isinstance(fn.body[0].value.value, str)) else fn.body
    names = {n.id for s in stmts for n in ast.walk(s) if isinstance(n, ast.Name)}

    assert "MOEX_TICKERS" not in names, \
        "get_live_price is routing on the literal set again"
    assert "asset_class" in names, \
        "get_live_price no longer routes by asset class"


@pytest.mark.asyncio
async def test_futures_resolve_their_exchange_code(monkeypatch):
    """ISS addresses futures by SECID ("GZZ6"), not the readable "GAZR-12.26".

    Asking with the readable form returns an empty result rather than a 404, so
    a wrong symbol looked exactly like "no data for this contract".
    """
    called = {}

    async def fake_secid(ticker):
        called["ticker"] = ticker
        return "GZZ6"

    import app.services.backtesting_real as br
    monkeypatch.setattr(br, "_forts_secid", fake_secid)

    class FakeResponse:
        @staticmethod
        def json():
            return {"marketdata": {"data": [["GZZ6", 9961.0, 10000.0, 9900.0,
                                             9950.0, 12345]]}}

    class FakeClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def get(self, *a, **kw):
            return FakeResponse()

    monkeypatch.setattr(live_price.httpx, "AsyncClient", lambda **kw: FakeClient())

    q = await live_price._moex_futures_price("GAZR-12.26")
    assert q is not None
    assert called["ticker"] == "GAZR-12.26", "the readable form must be resolved"
    assert q["price"] == 9961.0
    assert "GZZ6" in q["source"], "the source should name the contract it used"


@pytest.mark.asyncio
async def test_missing_last_price_is_none_not_a_fabricated_quote(monkeypatch):
    """Outside trading hours LAST comes back null. Returning a quote with a
    None price would put that straight into a signal's entry."""
    async def fake_secid(ticker):
        return "GZZ6"

    import app.services.backtesting_real as br
    monkeypatch.setattr(br, "_forts_secid", fake_secid)

    class FakeResponse:
        @staticmethod
        def json():
            return {"marketdata": {"data": [["GZZ6", None, None, None, None, 0]]}}

    class FakeClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def get(self, *a, **kw):
            return FakeResponse()

    monkeypatch.setattr(live_price.httpx, "AsyncClient", lambda **kw: FakeClient())
    assert await live_price._moex_futures_price("GAZR-12.26") is None
