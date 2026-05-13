"""Article Evolution Log — tracks MQL5 articles processed by the evolutionary protocol.

Each article is classified, components extracted, and architecture evolved.
This log provides traceability: which article contributed what to the system.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class ProcessedArticle:
    """Record of an article processed through the evolutionary protocol."""
    article_id: int             # MQL5 article number (e.g. 22211)
    url: str                    # Full URL
    title: str                  # Article title
    main_strategy_id: int       # Primary Strategy ID (1-7)
    secondary_ids: list[int]    # Secondary Strategy IDs
    components_extracted: list[str]  # New/strengthened components
    branch_impact: str          # Which branches affected
    evolution_summary: str      # What changed in architecture
    processed_at: str           # ISO timestamp


class ArticleEvolutionLog:
    """Persistent log of all articles processed by the evolutionary protocol."""

    def __init__(self):
        self.articles: list[ProcessedArticle] = []
        self._init_history()

    def _init_history(self):
        """Pre-load articles that were processed before this log existed."""
        self.articles = [
            ProcessedArticle(
                article_id=19738,
                url="https://www.mql5.com/ru/articles/19738",
                title="Вероятностный анализ свечных паттернов и пробоев",
                main_strategy_id=4,
                secondary_ids=[2, 6, 7],
                components_extracted=["pattern_probability", "volume_confirmation", "instrument_dna", "breakout_confirmation"],
                branch_impact="Breakout(4) strengthened, Mean Reversion(2) + Statistical(6) enriched",
                evolution_summary="Added 4 emerging components: pattern probability engine, volume confirmation, instrument DNA profiler, breakout confirmation logic. Components: 17→21.",
                processed_at="2026-05-13T12:00:00Z",
            ),
            ProcessedArticle(
                article_id=22211,
                url="https://www.mql5.com/ru/articles/22211",
                title="Сеточный советник на клеточном автомате с онлайн-обучением",
                main_strategy_id=7,
                secondary_ids=[1, 2, 3, 5],
                components_extracted=["cellular_automaton", "online_learning", "strategy_archetypes", "network_health", "genome_mutation", "consensus_dynamics", "population_logic"],
                branch_impact="ML/AI(7) BREAKTHROUGH: population logic activated. Trend(1), MeanRev(2), Range(3), MultiInd(5) enriched via archetypes.",
                evolution_summary="BREAKTHROUGH article. 6 new + 1 upgraded components. Cellular automaton with 10K agents, online learning without interruption, genome mutation, strategy archetype system. Population logic promoted: planned→emerging. Architecture: 21→27 components.",
                processed_at="2026-05-13T13:00:00Z",
            ),
        ]

    def record(
        self,
        article_id: int,
        url: str,
        title: str,
        main_strategy_id: int,
        secondary_ids: list[int],
        components_extracted: list[str],
        branch_impact: str,
        evolution_summary: str,
    ) -> ProcessedArticle:
        """Record a newly processed article."""
        # Check if already processed
        if any(a.article_id == article_id for a in self.articles):
            logger.info(f"Article {article_id} already processed, skipping")
            existing = next(a for a in self.articles if a.article_id == article_id)
            return existing

        entry = ProcessedArticle(
            article_id=article_id,
            url=url,
            title=title,
            main_strategy_id=main_strategy_id,
            secondary_ids=secondary_ids,
            components_extracted=components_extracted,
            branch_impact=branch_impact,
            evolution_summary=evolution_summary,
            processed_at=datetime.now(timezone.utc).isoformat(),
        )
        self.articles.append(entry)
        logger.info(f"Article #{article_id} processed: {title} → Strategy ID {main_strategy_id}")
        return entry

    def is_processed(self, article_id: int) -> bool:
        return any(a.article_id == article_id for a in self.articles)

    def get_all(self) -> list[dict]:
        return [
            {
                "article_id": a.article_id,
                "url": a.url,
                "title": a.title,
                "main_strategy_id": a.main_strategy_id,
                "secondary_ids": a.secondary_ids,
                "components_extracted": a.components_extracted,
                "branch_impact": a.branch_impact,
                "evolution_summary": a.evolution_summary,
                "processed_at": a.processed_at,
            }
            for a in self.articles
        ]

    def get_stats(self) -> dict:
        total = len(self.articles)
        by_strategy: dict[int, int] = {}
        all_components: set[str] = set()
        for a in self.articles:
            by_strategy[a.main_strategy_id] = by_strategy.get(a.main_strategy_id, 0) + 1
            all_components.update(a.components_extracted)
        return {
            "total_articles_processed": total,
            "articles_by_strategy_id": by_strategy,
            "total_unique_components": len(all_components),
            "component_list": sorted(all_components),
        }


# Singleton
article_log = ArticleEvolutionLog()
