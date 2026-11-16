"""Posts from a public VK community wall, in the shape the pipeline expects.

Why VK at all
-------------
The Telegram side keeps running into channels this network cannot reach: three
of seventeen monitored ones answer nothing at all. VK is a Russian service and
answers directly — measured 2026-11-16, `api.vk.com` returned 200 from the
developer's own connection with no proxy.

Why the API and not the web
---------------------------
There is no VK equivalent of `t.me/s/`. `vk.com/<group>` and `m.vk.com/<group>`
both return 200 with a JavaScript shell: the strings `wall_post` and
`post_text` appear in the bundle, never in the markup. Scraping would need a
headless browser for every poll. The API is the only sane path, and it refuses
anonymous reads — `wall.get` without a token answers

    {"error": {"error_code": 15, "error_msg": "Access denied: token required"}}

So this needs VK_SERVICE_TOKEN. Getting one is an account action and belongs to
the owner, and it is no longer done where the old guides say: VK moved
standalone apps off dev.vk.com into the VK ID business cabinet, which issues
the service key when the app is created (id.vk.ru -> Мои приложения ->
Добавить приложение). A service key reads public walls and nothing else — it
cannot touch messages, friends or anything private, which is exactly the
authority this module should have.

That cabinet also wants a verified VK Бизнес ID profile: unverified, apps are
blocked 60 days after the first one is created. So this source can go dark for
a reason that has nothing to do with this code, which is why a rejected key
gets its own message below rather than being folded into "no token".

`wall.get` accepts a service key — stated on its own documentation page
alongside `filter` and the count ceiling of 100, both of which fetch_wall
honours.

Shape
-----
`fetch_wall` returns the same `{id, text, date}` dicts as
scripts/fetch_public.fetch_channel, so the parser, the freshness window, the
rejection log and the trial track all work unchanged. The id is
"vk:<owner>_<post>", unique across both networks.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

API = "https://api.vk.com/method/"
VERSION = "5.199"

# VK counts requests per second per token, not per method. Three is the
# documented ceiling for a service key; polling a dozen groups in a loop
# crosses it easily, so the pause is applied by `fetch_many` rather than left
# to the caller to remember.
RATE_PER_SEC = 3
_PAUSE = 1.0 / RATE_PER_SEC

# VK error codes worth naming. Anything else is reported with its own message.
# Measured against the live API on 2026-11-16: a wrong or expired key is
# code 5, not 15, and its message ("User authorization failed") says nothing
# about which token. Naming it saves the owner guessing.
ERR_BAD_TOKEN = 5
ERR_TOKEN_REQUIRED = 15
ERR_TOO_MANY = 6
ERR_GROUP_BLOCKED = 203
ERR_NOT_FOUND = 100


class VkUnavailable(RuntimeError):
    """The wall cannot be read, and retrying will not change that."""


class VkThrottled(RuntimeError):
    """Rate limited — the same call may well succeed a moment later."""


def _strip(text: str) -> str:
    """VK gives plain text with its own markup for links and mentions.

    `[club1|caption]` and `[id5|Name]` render as the caption, so the brackets
    have to go or every mention lands in the middle of a price line.
    """
    s = re.sub(r"\[(?:id|club|public)\d+\|([^\]]*)\]", r"\1", text or "")
    return s.replace("&quot;", '"').replace("&amp;", "&").strip()


def _check(body: dict, group: str) -> dict:
    err = body.get("error") or {}
    if not err:
        return body
    code = err.get("error_code")
    msg = err.get("error_msg", "")
    if code == ERR_TOKEN_REQUIRED:
        raise VkUnavailable(
            "VK_SERVICE_TOKEN не задан — стены читать нечем")
    if code == ERR_BAD_TOKEN:
        raise VkUnavailable(
            "VK_SERVICE_TOKEN недействителен или просрочен — возьмите "
            "сервисный ключ заново в настройках приложения")
    if code == ERR_TOO_MANY:
        raise VkThrottled(f"VK: слишком часто ({msg})")
    if code in (ERR_NOT_FOUND, ERR_GROUP_BLOCKED):
        raise VkUnavailable(f"@{group}: {msg}")
    raise VkUnavailable(f"@{group}: VK error {code}: {msg}")


async def fetch_wall(group: str, limit: int = 30) -> list[dict]:
    """Newest-first posts from a public community wall.

    `group` is the screen name as it appears in the address (vk.com/forex ->
    "forex"), with or without a leading "vk:" or "@".
    """
    name = re.sub(r"^(?:vk:|@)", "", (group or "").strip())
    if not name:
        raise VkUnavailable("пустое имя сообщества")
    token = (settings.vk_service_token or "").strip()
    if not token:
        raise VkUnavailable(
            "VK_SERVICE_TOKEN не задан: создайте приложение в кабинете VK ID "
            "(id.vk.ru → Мои приложения → Добавить приложение) и возьмите "
            "«Сервисный ключ доступа» из карточки приложения")

    params = {
        "domain": name,
        # `count` is capped at 100 per call by the API; nothing here needs more,
        # and the freshness window throws away most of what arrives anyway.
        "count": max(1, min(int(limit), 100)),
        "filter": "owner",     # the community's own posts, not visitors'
        "extended": 0,
        "v": VERSION,
    }
    # The key rides in the header, never in the query string. VK echoes the
    # query back inside its own error bodies (`request_params`), and a URL is
    # the part of a request that proxies and access logs keep by default — a
    # non-expiring key does not belong in either. Measured 2026-11-16: sent
    # this way a bad key answers error 5, not 15, so the header is genuinely
    # read and not quietly ignored in favour of the parameter.
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(API + "wall.get", params=params,
                                    headers=headers)
    except Exception as e:
        # A network failure is not the same as a wall that cannot be read; the
        # caller should retry this one.
        raise VkThrottled(f"@{name}: сеть недоступна ({type(e).__name__})") from e

    body = _check(resp.json(), name)
    items = (body.get("response") or {}).get("items") or []

    posts = []
    for it in items:
        text = _strip(it.get("text", ""))
        if not text:
            continue       # photo-only post: nothing to parse
        ts = it.get("date")
        when = (datetime.fromtimestamp(ts, tz=timezone.utc)
                if isinstance(ts, (int, float)) and ts > 0 else None)
        posts.append({
            "id": f"vk:{it.get('owner_id')}_{it.get('id')}",
            "text": text,
            "date": when,
        })
    if not posts and items:
        logger.info(f"@{name}: {len(items)} постов, ни одного с текстом")
    return posts


async def fetch_many(groups: list[str], limit: int = 30) -> dict[str, list[dict]]:
    """Several walls, spaced out so the token is not throttled.

    Returns only the ones that answered; unreadable walls are logged and left
    out, because the caller's job is to parse what arrived, not to decide what
    a VK error code meant.
    """
    out: dict[str, list[dict]] = {}
    for i, g in enumerate(groups):
        if i:
            await asyncio.sleep(_PAUSE)
        try:
            out[g] = await fetch_wall(g, limit)
        except VkThrottled as e:
            logger.warning(f"{e} — пропускаю до следующего прогона")
        except VkUnavailable as e:
            logger.info(f"{e}")
    return out
