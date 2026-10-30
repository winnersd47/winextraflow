"""The MEXC adapter, and the one property that protects real money.

MEXC has no spot testnet — `api-testnet.mexc.com` and `api-sandbox.mexc.com`
do not resolve (checked 2026-10-29), only the futures host has one. So the
adapter takes no `testnet` argument, and `execution._get_adapter` turns the
resulting TypeError into DemoAdapter for any account marked virtual.

That is the whole safety mechanism, and it is one keyword argument away from
being silently undone: adding `testnet=False` to the signature to "match the
others" would make every paper account place live orders on a real book. The
first test here exists to stop exactly that.
"""
import hashlib
import hmac
import inspect
from urllib.parse import parse_qsl

import httpx
import pytest

from app.models.exchange_account import ExchangeName
from app.services.exchanges import MexcAdapter
from app.services.exchanges.demo import DemoAdapter
from app.services.execution import _get_adapter

FILLED = {"orderId": 77, "executedQty": "0.5", "cummulativeQuoteQty": "38750.0"}


class _Resp:
    def __init__(self, payload, status=200):
        self._p, self.status_code = payload, status
        self.text = str(payload)

    def json(self):
        return self._p


class _Account:
    """Enough of ExchangeAccount for _get_adapter, with plaintext keys."""

    def __init__(self, exchange, testnet):
        self.exchange = exchange
        self.is_testnet = testnet
        self.label = "test"
        self.api_key_encrypted = "k"
        self.api_secret_encrypted = "s"


@pytest.fixture
def _plaintext_keys(monkeypatch):
    import app.services.execution as ex
    monkeypatch.setattr(ex, "decrypt_value", lambda v: v)


# ── the safety property ────────────────────────────────────────────────────

def test_adapter_refuses_a_testnet_argument():
    """There is no MEXC spot testnet, so the adapter must not pretend to one."""
    params = inspect.signature(MexcAdapter.__init__).parameters
    assert "testnet" not in params, (
        "у MEXC нет spot-testnet; если адаптер примет testnet=, бумажный счёт "
        "начнёт отправлять ордера на реальный стакан"
    )
    with pytest.raises(TypeError):
        MexcAdapter("k", "s", testnet=True)


def test_a_paper_account_never_reaches_live_mexc(_plaintext_keys):
    """The property that keyword absence buys: virtual routes to Demo."""
    got = _get_adapter(_Account(ExchangeName.MEXC, testnet=True))
    assert isinstance(got, DemoAdapter), (
        "счёт, помеченный как бумажный, получил живой адаптер MEXC"
    )


def test_an_explicitly_live_account_gets_the_real_adapter(_plaintext_keys):
    got = _get_adapter(_Account(ExchangeName.MEXC, testnet=False))
    assert isinstance(got, MexcAdapter)


# ── signing ────────────────────────────────────────────────────────────────

def test_signature_covers_the_query_exactly_as_sent():
    """Signed string and request must come from the same ordered mapping."""
    a = MexcAdapter("key", "secret")
    signed = a._sign({"symbol": "BTCUSDT", "side": "BUY"})

    sig = signed.pop("signature")
    from urllib.parse import urlencode
    expected = hmac.new(b"secret", urlencode(signed).encode(),
                        hashlib.sha256).hexdigest()
    assert sig == expected


def test_signing_adds_timestamp_and_recv_window():
    signed = MexcAdapter("k", "s")._sign({})
    assert signed["timestamp"] > 0
    assert signed["recvWindow"] == 5000


def test_the_key_travels_in_the_header_not_the_query():
    a = MexcAdapter("my-key", "s")
    assert a.client.headers["X-MEXC-APIKEY"] == "my-key"
    assert "my-key" not in str(a._sign({"symbol": "BTCUSDT"}))


# ── orders ─────────────────────────────────────────────────────────────────

def _stub(monkeypatch, payload, status=200, capture=None):
    async def _call(_self, _url, params=None, **k):
        if capture is not None:
            capture.update(params or {})
        return _Resp(payload, status)

    monkeypatch.setattr(httpx.AsyncClient, "post", _call)
    monkeypatch.setattr(httpx.AsyncClient, "get", _call)
    monkeypatch.setattr(httpx.AsyncClient, "delete", _call)


@pytest.mark.asyncio
async def test_market_order_reports_the_average_fill_not_the_request(monkeypatch):
    """quote/executed is the real fill. Echoing the requested price hides slippage."""
    _stub(monkeypatch, FILLED)
    r = await MexcAdapter("k", "s").place_market_order("BTCUSDT", "buy", 0.5)

    assert r.status == "filled"
    assert r.filled_quantity == pytest.approx(0.5)
    assert r.filled_price == pytest.approx(77500.0)   # 38750 / 0.5
    assert r.exchange_order_id == "77"


@pytest.mark.asyncio
async def test_a_rejected_order_carries_the_exchange_wording(monkeypatch):
    """A precision or min-notional rejection must say so, not "failed"."""
    _stub(monkeypatch, {"code": -1013, "msg": "Invalid quantity"}, status=400)
    r = await MexcAdapter("k", "s").place_market_order("BTCUSDT", "buy", 0.000001)

    assert r.status == "failed"
    assert "Invalid quantity" in r.error
    assert r.filled_quantity is None


@pytest.mark.asyncio
async def test_a_network_failure_is_failed_not_an_exception(monkeypatch):
    async def _boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx.AsyncClient, "post", _boom)
    r = await MexcAdapter("k", "s").place_market_order("BTCUSDT", "buy", 1)
    assert r.status == "failed" and r.error


@pytest.mark.asyncio
async def test_unfilled_limit_order_is_pending(monkeypatch):
    _stub(monkeypatch, {"orderId": 9, "executedQty": "0"})
    r = await MexcAdapter("k", "s").place_limit_order("BTCUSDT", "buy", 1.0, 60000.0)
    assert r.status == "pending" and r.price == 60000.0


@pytest.mark.asyncio
async def test_limit_order_sends_a_time_in_force(monkeypatch):
    """Without it MEXC rejects the order outright."""
    seen = {}
    _stub(monkeypatch, {"orderId": 9, "executedQty": "0"}, capture=seen)
    await MexcAdapter("k", "s").place_limit_order("BTCUSDT", "buy", 1.0, 60000.0)
    assert seen.get("timeInForce") == "GTC"
    assert seen.get("type") == "LIMIT"


# ── balance ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_balance_counts_free_not_locked(monkeypatch):
    """`locked` sits in open orders; staking it would commit money twice."""
    _stub(monkeypatch, {"balances": [
        {"asset": "BTC", "free": "1.0", "locked": "0"},
        {"asset": "USDT", "free": "250.5", "locked": "1000.0"},
    ]})
    assert await MexcAdapter("k", "s").get_balance("USDT") == pytest.approx(250.5)


@pytest.mark.asyncio
async def test_unreadable_balance_is_zero_not_a_crash(monkeypatch):
    _stub(monkeypatch, {"code": -2015, "msg": "Invalid API-key"}, status=401)
    assert await MexcAdapter("k", "s").get_balance("USDT") == 0.0


@pytest.mark.asyncio
async def test_missing_asset_is_zero(monkeypatch):
    _stub(monkeypatch, {"balances": [{"asset": "BTC", "free": "1.0"}]})
    assert await MexcAdapter("k", "s").get_balance("USDT") == 0.0


@pytest.mark.asyncio
async def test_ticker_price_is_zero_when_unavailable(monkeypatch):
    _stub(monkeypatch, {"code": -1121, "msg": "invalid symbol"}, status=400)
    assert await MexcAdapter("k", "s").get_ticker_price("NOPE") == 0.0


@pytest.mark.asyncio
async def test_cancel_reports_success_by_status(monkeypatch):
    _stub(monkeypatch, {"orderId": 77}, status=200)
    assert await MexcAdapter("k", "s").cancel_order("BTCUSDT", "77") is True
    _stub(monkeypatch, {"code": -2011, "msg": "Unknown order"}, status=400)
    assert await MexcAdapter("k", "s").cancel_order("BTCUSDT", "77") is False


def test_mexc_is_registered_everywhere():
    """A member of the enum with no entry in the map silently becomes Demo."""
    import app.services.execution as ex
    assert ExchangeName.MEXC.value == "mexc"
    assert "MexcAdapter" in inspect.getsource(ex._get_adapter)
