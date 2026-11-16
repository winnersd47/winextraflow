"""VK walls must arrive in the same shape as Telegram posts, or nothing reuses.

The whole point of this source is that one pipeline handles both networks: the
parser, the 48-hour window, the rejection log and the trial track were built
for `{id, text, date}` dicts and should not learn that a second network exists.

The error codes below are the ones the live API actually returned on
2026-11-16, not guesses — a wrong key is code 5, a missing one is 15, and the
two need different advice because only one of them means "go and make a token".
"""
import asyncio

import httpx
import pytest

import app.services.vk_source as vk


def _post(pid, text, ts=1_794_000_000, owner=-123):
    return {"id": pid, "owner_id": owner, "text": text, "date": ts}


class _Resp:
    def __init__(self, payload):
        self._p, self.status_code = payload, 200

    def json(self):
        return self._p


def _api(monkeypatch, payload, token="service-key", capture=None):
    monkeypatch.setattr(vk.settings, "vk_service_token", token)

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, _url, params=None, **k):
            if capture is not None:
                capture.update(params or {})
            return _Resp(payload)

    monkeypatch.setattr(httpx, "AsyncClient", _Client)


# ── shape ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_posts_match_the_telegram_shape(monkeypatch):
    _api(monkeypatch, {"response": {"items": [_post(7, "BUY EURUSD @ 1.08")]}})
    (p,) = await vk.fetch_wall("forex", 5)

    assert set(p) == {"id", "text", "date"}, "форма разошлась с Telegram-источником"
    assert p["text"] == "BUY EURUSD @ 1.08"
    assert p["date"].tzinfo is not None, "дата без таймзоны сломает окно свежести"


@pytest.mark.asyncio
async def test_ids_cannot_collide_with_telegram_ones(monkeypatch):
    """Both networks write into one rejection log, keyed by message id."""
    _api(monkeypatch, {"response": {"items": [_post(7, "BUY EURUSD @ 1.08")]}})
    (p,) = await vk.fetch_wall("forex", 5)
    assert p["id"].startswith("vk:") and p["id"] == "vk:-123_7"


@pytest.mark.asyncio
async def test_a_vk_post_parses_with_the_existing_parser(monkeypatch):
    """The reason the shape matters: no second parser."""
    from app.services.telegram import telegram_parser

    _api(monkeypatch, {"response": {"items": [
        _post(1, "🔥 EURCAD - SELL @ 1.56842\nSL: 1.57700\nTP: 1.55000")]}})
    (p,) = await vk.fetch_wall("forex", 5)
    parsed = telegram_parser.parse_message(p["text"])
    assert parsed is not None and parsed.ticker == "EURCAD"


# ── VK's own markup ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mention_markup_is_unwrapped(monkeypatch):
    """`[club1|caption]` left whole would sit in the middle of a price line."""
    _api(monkeypatch, {"response": {"items": [
        _post(1, "[club1|Наш канал] BUY EURUSD @ 1.08 [id5|Иван]")]}})
    (p,) = await vk.fetch_wall("forex", 5)
    assert "[club1" not in p["text"] and "Наш канал" in p["text"]
    assert "Иван" in p["text"]


@pytest.mark.asyncio
async def test_a_photo_only_post_is_dropped(monkeypatch):
    _api(monkeypatch, {"response": {"items": [
        _post(1, ""), _post(2, "BUY EURUSD @ 1.08")]}})
    assert len(await vk.fetch_wall("forex", 5)) == 1


@pytest.mark.asyncio
async def test_a_post_without_a_date_is_reported_as_undated(monkeypatch):
    """None, never "now": the caller drops it rather than treating it as fresh."""
    _api(monkeypatch, {"response": {"items": [_post(1, "BUY EURUSD", ts=0)]}})
    (p,) = await vk.fetch_wall("forex", 5)
    assert p["date"] is None


# ── request shape ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_only_the_community_s_own_posts_are_requested(monkeypatch):
    """Without filter=owner the wall returns visitors' posts as signals."""
    seen = {}
    _api(monkeypatch, {"response": {"items": []}}, capture=seen)
    await vk.fetch_wall("vk:forex", 5)
    assert seen["filter"] == "owner"
    assert seen["domain"] == "forex", "префикс vk: должен сниматься"


@pytest.mark.asyncio
async def test_count_is_clamped_to_the_api_ceiling(monkeypatch):
    seen = {}
    _api(monkeypatch, {"response": {"items": []}}, capture=seen)
    await vk.fetch_wall("forex", 5000)
    assert seen["count"] == 100


@pytest.mark.asyncio
async def test_the_token_is_not_logged_into_the_id(monkeypatch):
    _api(monkeypatch, {"response": {"items": [_post(1, "BUY")]}}, token="secret-key")
    (p,) = await vk.fetch_wall("forex", 5)
    assert "secret-key" not in p["id"] and "secret-key" not in p["text"]


# ── errors, as the live API returns them ───────────────────────────────────

@pytest.mark.asyncio
async def test_a_missing_token_says_how_to_get_one(monkeypatch):
    _api(monkeypatch, {"response": {"items": []}}, token="")
    with pytest.raises(vk.VkUnavailable) as e:
        await vk.fetch_wall("forex", 5)
    assert "VK_SERVICE_TOKEN" in str(e.value)


@pytest.mark.asyncio
async def test_a_wrong_token_is_told_apart_from_a_missing_one(monkeypatch):
    """Code 5, measured live. Its own message names no token at all."""
    _api(monkeypatch, {"error": {"error_code": 5,
                                 "error_msg": "User authorization failed"}})
    with pytest.raises(vk.VkUnavailable) as e:
        await vk.fetch_wall("forex", 5)
    assert "недействителен" in str(e.value) or "просрочен" in str(e.value)


@pytest.mark.asyncio
async def test_rate_limiting_is_retryable_not_fatal(monkeypatch):
    """A throttled call must not write the source off as unreadable."""
    _api(monkeypatch, {"error": {"error_code": 6, "error_msg": "Too many requests"}})
    with pytest.raises(vk.VkThrottled):
        await vk.fetch_wall("forex", 5)


@pytest.mark.asyncio
async def test_an_unknown_group_is_permanent(monkeypatch):
    _api(monkeypatch, {"error": {"error_code": 100, "error_msg": "not found"}})
    with pytest.raises(vk.VkUnavailable):
        await vk.fetch_wall("nope", 5)


@pytest.mark.asyncio
async def test_a_network_failure_is_retryable(monkeypatch):
    monkeypatch.setattr(vk.settings, "vk_service_token", "k")

    class _Dead:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "AsyncClient", _Dead)
    with pytest.raises(vk.VkThrottled):
        await vk.fetch_wall("forex", 5)


# ── routing ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_the_backfill_routes_by_prefix(monkeypatch):
    """One monitored list, two networks, one pipeline."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts import tg_backfill as bf

    called = {}

    async def _tg(name, limit=30):
        called["tg"] = name
        return []

    async def _vk(name, limit=30):
        called["vk"] = name
        return []

    monkeypatch.setattr(bf, "fetch_channel", _tg)
    monkeypatch.setattr(vk, "fetch_wall", _vk)

    await bf.fetch_source("beststocksru", 10)
    await bf.fetch_source("vk:forex", 10)
    assert called == {"tg": "beststocksru", "vk": "vk:forex"}


@pytest.mark.asyncio
async def test_many_walls_are_spaced_out(monkeypatch):
    """VK counts requests per second per token, not per method."""
    _api(monkeypatch, {"response": {"items": []}})
    monkeypatch.setattr(vk, "_PAUSE", 0.01)

    start = asyncio.get_event_loop().time()
    await vk.fetch_many(["a", "b", "c"], 5)
    assert asyncio.get_event_loop().time() - start >= 0.02


@pytest.mark.asyncio
async def test_one_unreadable_wall_does_not_stop_the_rest(monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(vk.settings, "vk_service_token", "k")
    monkeypatch.setattr(vk, "_PAUSE", 0)

    async def _one(name, limit=30):
        calls["n"] += 1
        if name == "bad":
            raise vk.VkUnavailable("нет такой группы")
        return [{"id": f"vk:{name}", "text": "BUY", "date": None}]

    monkeypatch.setattr(vk, "fetch_wall", _one)
    got = await vk.fetch_many(["good", "bad", "other"], 5)
    assert set(got) == {"good", "other"} and calls["n"] == 3
