"""Hashtags for a signal card, ordered by how much they are worth.

Cards used to carry three tags — `#TICKER #market #WinExtraFlow` — which is
enough to find one instrument and nothing else. A reader looking for "all the
forex shorts" or "everything on gold" had no way in, and Telegram's own search
works on exactly these.

Two constraints shape this:

* **Budget.** A card goes out as a photo or video caption, where Telegram's
  limit is 1024 characters, not the 4096 a plain message gets. This project has
  already lost whole cards to MEDIA_CAPTION_TOO_LONG — every card carrying a
  geometry baseline was silently rejected and the signal never published. So
  tags are generated in priority order and the caller takes the prefix that
  fits; `fit()` does that.

* **Order.** The first tags must be the ones a reader would actually type. The
  ticker and the market are worth more than a mood word, so the tail is where
  the broad ones live — and the tail is what gets dropped first.

Russian and English duplicates are deliberate: the channel's readers search in
both, and `#форекс` and `#forex` are different tags to Telegram.
"""

import re

from app.services.instruments import asset_class

# The two sides of a currency pair are worth their own tags: someone following
# the rouble wants every USDRUB and EURRUB card, not a search per pair.
_PAIR_LEN = 6

# Broad audience tags. Last in the list, first to be dropped: they carry the
# least information and cost the same characters as a ticker.
_BROAD = ("#трейдинг", "#trading", "#инвестиции", "#investing",
          "#аналитика", "#торговыесигналы", "#tradingsignals")

_CLASS_TAGS: dict[str, tuple[str, ...]] = {
    "forex":     ("#forex", "#форекс", "#валюты", "#currencies", "#FX"),
    "commodity": ("#commodities", "#сырьё", "#металлы", "#commodity"),
    "crypto":    ("#crypto", "#крипта", "#криптовалюты", "#cryptocurrency",
                  "#Binance"),
    "futures":   ("#фьючерсы", "#futures", "#FORTS", "#MOEX", "#срочныйрынок"),
    "moex":      ("#MOEX", "#Мосбиржа", "#акцииРФ", "#российскиеакции",
                  "#фондовыйрынок"),
    "stocks":    ("#stocks", "#акции", "#USstocks", "#фондовыйрынок"),
}

# Instruments people follow by name rather than by symbol.
_ALIASES: dict[str, tuple[str, ...]] = {
    "XAUUSD": ("#золото", "#gold", "#XAU"),
    "XAGUSD": ("#серебро", "#silver", "#XAG"),
    "BTCUSDT": ("#BTC", "#биткоин", "#bitcoin"),
    "ETHUSDT": ("#ETH", "#эфир", "#ethereum"),
}


def _tag(symbol: str) -> str:
    """`RTS-12.26` -> `#RTS_12_26`.

    Telegram ends a hashtag at the first character that is not a letter, digit
    or underscore, so `#RTS-12.26` renders as the tag `#RTS` followed by the
    loose text `-12.26` — it looks like a typo and does not search as the
    contract. Futures codes are the only tickers here that contain punctuation.
    """
    return "#" + re.sub(r"[^0-9A-Za-zА-Яа-яЁё_]+", "_", symbol).strip("_")


def _base_symbol(ticker: str) -> str | None:
    """`RTS-12.26` -> `RTS`, `BTCUSDT` -> `BTC`. None when nothing is gained."""
    t = (ticker or "").upper()
    if "-" in t:
        return t.split("-", 1)[0] or None
    for quote in ("USDT", "BUSD"):
        if t.endswith(quote) and len(t) > len(quote):
            return t[: -len(quote)]
    return None


def build_tags(ticker: str, action: str = "", wef: int | None = None) -> list[str]:
    """Tags for one signal, most specific first."""
    t = (ticker or "").upper()
    if not t:
        return ["#WinExtraFlow"]

    tags: list[str] = [_tag(t)]

    base = _base_symbol(t)
    if base and base != t:
        tags.append(_tag(base))

    tags.extend(_ALIASES.get(t, ()))

    cls = asset_class(t)
    if cls in ("forex", "commodity") and len(t) == _PAIR_LEN:
        tags += [_tag(t[:3]), _tag(t[3:])]

    tags.extend(_CLASS_TAGS.get(cls, ()))

    a = (action or "").lower()
    if a in ("buy", "long"):
        tags += ["#лонг", "#long", "#buy", "#покупка"]
    elif a in ("sell", "short"):
        tags += ["#шорт", "#short", "#sell", "#продажа"]

    # A band, not the exact score: "#WEF76" would be a tag with one post in it.
    if wef is not None:
        tags.append("#WEF80плюс" if wef >= 80 else
                    "#WEF70плюс" if wef >= 70 else "#WEF")

    tags.append("#сигнал")
    tags.append("#signal")
    tags.extend(_BROAD)
    tags.append("#WinExtraFlow")

    seen, out = set(), []
    for tag in tags:
        if tag.lower() not in seen:
            seen.add(tag.lower())
            out.append(tag)
    return out


def fit(tags: list[str], budget: int, *, keep_brand: bool = True) -> str:
    """As many tags as `budget` characters allow, joined by spaces.

    `#WinExtraFlow` is the channel's own tag and the one worth keeping when
    almost nothing fits, so it is reserved up front rather than dropped with
    the rest of the tail. The reservation is still only a preference: when the
    budget is smaller than the brand tag itself, the result is empty rather
    than over — the caller's budget is the caption limit, and going over it
    means Telegram refuses the whole card.
    """
    brand = "#WinExtraFlow"
    wants_brand = keep_brand and brand in tags
    if budget <= 0 or (wants_brand and len(brand) > budget and
                       all(len(t) > budget for t in tags)):
        return ""

    rest = [t for t in tags if t != brand]
    reserve = len(brand) + 1 if wants_brand and len(brand) <= budget else 0

    chosen: list[str] = []
    used = 0
    for tag in rest:
        cost = len(tag) + (1 if chosen else 0)
        if used + cost + reserve > budget:
            break
        chosen.append(tag)
        used += cost

    if reserve:
        chosen.append(brand)
    elif not chosen and brand in tags and len(brand) <= budget:
        chosen = [brand]
    return " ".join(chosen)


def tag_line(ticker: str, action: str = "", wef: int | None = None,
             budget: int = 240) -> str:
    """Ready-to-append tag line, trimmed to `budget` characters."""
    return fit(build_tags(ticker, action, wef), budget)
