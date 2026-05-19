"""Auto-Evolution Service — fetches new MQL5 articles and evolves architecture.

Called on each dashboard load. Checks MQL5 for new articles,
classifies them by Strategy ID, extracts components,
and updates the Evolutionary Registry.

Rate-limited: max 1 fetch per hour to avoid hammering MQL5.
"""

import logging
import re
import time
from datetime import datetime, timezone

import httpx

from app.services.quant.article_log import article_log
from app.services.quant.evolution import evolutionary_registry

logger = logging.getLogger(__name__)

MQL5_ARTICLES_URL = "https://www.mql5.com/ru/articles"
_last_fetch_time: float = 0
_FETCH_COOLDOWN = 3600  # 1 hour between fetches
_last_result: dict | None = None


# Keywords for auto-classification
STRATEGY_KEYWORDS = {
    1: ["trend", "тренд", "скользящ", "moving average", "EMA", "SMA", "ADX", "supertrend"],
    2: ["mean reversion", "возврат", "перекуп", "перепрод", "RSI", "oscillator", "осциллятор", "Stochastic"],
    3: ["range", "диапазон", "боков", "flat", "канал", "support", "resistance", "поддержк", "сопротивлен"],
    4: ["breakout", "пробой", "прорыв", "break of structure", "BOS", "ChOCh"],
    5: ["indicator", "индикатор", "MACD", "multi", "мульти", "strategy", "стратеги"],
    6: ["arbitrage", "арбитраж", "статистик", "statistical", "copula", "cointegrat", "корреляц"],
    7: ["neural", "нейрон", "machine learning", "ML", "AI", "ONNX", "deep learning", "reinforcement", "GPT", "LLM", "transformer"],
}

COMPONENT_PATTERNS = {
    "neural_network": r"нейрон|neural|deep learning",
    "onnx_model": r"ONNX|onnx",
    "price_action": r"Price Action|price action|свечн.*паттерн",
    "grid_trading": r"сетк|grid|мартингейл|martingale",
    "genetic_algorithm": r"генетич|genetic|эволюци|evolution",
    "indicator_custom": r"индикатор.*custom|пользовательск.*индикатор",
    "risk_management": r"риск.*менеджмент|risk.*management|стоп.?лосс",
    "multi_timeframe": r"мульти.*таймфрейм|multi.*timeframe",
    "volume_profile": r"профиль.*объём|volume.*profile",
    "order_flow": r"поток.*ордер|order.*flow",
    "regression_model": r"регрессия|regression|least.*square",
    "clustering": r"кластер|cluster|k-means",
    "bayesian": r"байес|bayesian|posterior",
    "sentiment": r"настроен|sentiment",
    "calendar_filter": r"календар|calendar|новост.*фильтр",
}


def _classify_article(title: str, description: str) -> tuple[int, list[int]]:
    """Classify article by Strategy ID from title+description."""
    text = f"{title} {description}".lower()
    scores = {sid: 0 for sid in range(1, 8)}
    for sid, keywords in STRATEGY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text:
                scores[sid] += 1
    sorted_ids = sorted(scores, key=scores.get, reverse=True)
    main_id = sorted_ids[0] if scores[sorted_ids[0]] > 0 else 5
    secondary = [sid for sid in sorted_ids[1:4] if scores[sid] > 0]
    return main_id, secondary


def _extract_components(title: str, description: str) -> list[str]:
    """Extract architectural components from article text."""
    text = f"{title} {description}"
    found = []
    for comp, pattern in COMPONENT_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            found.append(comp)
    return found


async def _fetch_mql5_articles() -> list[dict]:
    """Fetch latest articles from MQL5."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(MQL5_ARTICLES_URL, headers={
                "User-Agent": "WinExtraFlow/1.0 (Evolution Engine)",
                "Accept-Language": "ru",
            })
            if resp.status_code != 200:
                logger.warning(f"MQL5 fetch failed: {resp.status_code}")
                return []

            html = resp.text
            # Extract article links and titles
            # Pattern: /ru/articles/NNNNN with nearby title text
            articles = []
            for match in re.finditer(r'href="/ru/articles/(\d+)"[^>]*>([^<]+)</a>', html):
                article_id = int(match.group(1))
                title = match.group(2).strip()
                if title and len(title) > 10 and article_id > 1000:
                    articles.append({"id": article_id, "title": title})

            # Deduplicate by ID
            seen = set()
            unique = []
            for a in articles:
                if a["id"] not in seen:
                    seen.add(a["id"])
                    unique.append(a)
            return unique[:20]  # Top 20

    except Exception as e:
        logger.warning(f"MQL5 fetch error: {e}")
        return []


async def check_and_evolve() -> dict:
    """Main entry: check for new articles and evolve if found.

    Returns summary of what happened. Rate-limited to 1/hour.
    """
    global _last_fetch_time, _last_result

    now = time.time()
    if now - _last_fetch_time < _FETCH_COOLDOWN and _last_result:
        return _last_result

    _last_fetch_time = now

    articles = await _fetch_mql5_articles()
    if not articles:
        _last_result = {"status": "no_articles", "new_count": 0, "total_processed": article_log.get_stats()["total_articles_processed"]}
        return _last_result

    # Find new articles not yet processed
    new_articles = [a for a in articles if not article_log.is_processed(a["id"])]

    if not new_articles:
        _last_result = {
            "status": "up_to_date",
            "new_count": 0,
            "checked": len(articles),
            "total_processed": article_log.get_stats()["total_articles_processed"],
        }
        return _last_result

    # Process new articles
    processed = []
    for a in new_articles[:5]:  # Max 5 per cycle
        main_id, secondary_ids = _classify_article(a["title"], "")
        components = _extract_components(a["title"], "")

        entry = article_log.record(
            article_id=a["id"],
            url=f"https://www.mql5.com/ru/articles/{a['id']}",
            title=a["title"],
            main_strategy_id=main_id,
            secondary_ids=secondary_ids,
            components_extracted=components,
            branch_impact=f"Auto-classified: ID{main_id}",
            evolution_summary=f"Auto-evolution from MQL5 article #{a['id']}: {a['title'][:80]}",
        )

        # Strengthen branch in evolutionary registry
        for comp in components:
            if comp in evolutionary_registry.components:
                evolutionary_registry.components[comp].strength = min(
                    evolutionary_registry.components[comp].strength + 0.02, 1.0
                )

        processed.append({
            "id": a["id"],
            "title": a["title"],
            "strategy_id": main_id,
            "components": components,
        })

    _last_result = {
        "status": "evolved",
        "new_count": len(processed),
        "checked": len(articles),
        "processed": processed,
        "total_processed": article_log.get_stats()["total_articles_processed"],
    }

    logger.info(f"Auto-evolution: {len(processed)} new articles processed from MQL5")
    return _last_result
