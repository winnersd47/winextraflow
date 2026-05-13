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
            # ─── Batch: 13 articles processed 2026-05-13 ─────
            ProcessedArticle(
                article_id=22474,
                url="https://www.mql5.com/ru/articles/22474",
                title="ML-пайплайн в MQL5: от матриц до ONNX",
                main_strategy_id=7,
                secondary_ids=[1, 5],
                components_extracted=["onnx_inference", "feature_pipeline", "pca_compression"],
                branch_impact="ML/AI(7) ACCELERATING: production ML pipeline. LSTM+PCA+ONNX.",
                evolution_summary="ML inference pipeline: Python trains LSTM→ONNX, MQL5 runs PCA+StandardScaler+inference in-terminal. Separation of training/inference as architectural pattern.",
                processed_at="2026-05-13T14:00:00Z",
            ),
            ProcessedArticle(
                article_id=22562,
                url="https://www.mql5.com/ru/articles/22562",
                title="GDformer: внимание, память и рыночные паттерны",
                main_strategy_id=7,
                secondary_ids=[1, 2],
                components_extracted=["learnable_memory", "cross_attention_dictionary", "pattern_abstention", "sparse_attention"],
                branch_impact="ML/AI(7) BREAKTHROUGH: learnable market memory + abstention logic (refuse trade when no pattern).",
                evolution_summary="GDformer architecture: dictionary-based cross-attention O(TN) replaces O(T²). Learnable memory matches regimes. Sparse attention preserves absolute scores. 'No pattern' detection = risk-aware abstention.",
                processed_at="2026-05-13T14:01:00Z",
            ),
            ProcessedArticle(
                article_id=19697,
                url="https://www.mql5.com/ru/articles/19697",
                title="Интерактивное тестирование с статистическими уровнями",
                main_strategy_id=3,
                secondary_ids=[2, 5],
                components_extracted=["statistical_levels", "kde_mode_estimation", "zscore_signals"],
                branch_impact="Range(3) EVOLVING: statistical distribution layers for S/R detection.",
                evolution_summary="Z-score signal engine + KDE modal estimation + percentile-based support/resistance. Statistical approach to range detection.",
                processed_at="2026-05-13T14:02:00Z",
            ),
            ProcessedArticle(
                article_id=19931,
                url="https://www.mql5.com/ru/articles/19931",
                title="Архимедовы копулы в MQL5 для парного трейдинга",
                main_strategy_id=6,
                secondary_ids=[2, 7],
                components_extracted=["copula_dependency", "tail_dependency_model", "conditional_probability_signals"],
                branch_impact="Statistical(6) ACCELERATING: copula-based dependency modeling. Clayton/Gumbel/Frank tail analysis.",
                evolution_summary="6 Archimedean copula families for asymmetric tail dependency. Conditional probability triggers (0.05/0.95). Pairs trading via joint distribution analysis.",
                processed_at="2026-05-13T14:03:00Z",
            ),
            ProcessedArticle(
                article_id=20020,
                url="https://www.mql5.com/ru/articles/20020",
                title="Кодекс рыночных состояний: побитовое обучение",
                main_strategy_id=5,
                secondary_ids=[1, 7],
                components_extracted=["bitwise_pattern_encoding", "pattern_combination_synergy", "oscillator_decomposition"],
                branch_impact="MultiInd(5) EVOLVING: pattern synergy detection via bitwise combination of RSI+DeMarker signals.",
                evolution_summary="5 signal patterns from RSI+DeMarker decomposition. Bitwise encoding enables systematic combination testing. Forward-tested: avoids mutual pattern cancellation.",
                processed_at="2026-05-13T14:04:00Z",
            ),
            ProcessedArticle(
                article_id=19850,
                url="https://www.mql5.com/ru/articles/19850",
                title="ML-пайплайн: одновременность меток (label concurrency)",
                main_strategy_id=7,
                secondary_ids=[6],
                components_extracted=["label_uniqueness_weighting", "purged_kfold", "sequential_bootstrap", "temporal_overlap_correction"],
                branch_impact="ML/AI(7) CORE EVOLUTION: fundamental ML training improvement. Fixes IID violation in financial data.",
                evolution_summary="Triple-barrier label concurrency fix: uniqueness weighting, purged K-Fold CV, sequential bootstrap. Prevents overfitting from overlapping observation windows. Applies to ALL ML strategies.",
                processed_at="2026-05-13T14:05:00Z",
            ),
            ProcessedArticle(
                article_id=19589,
                url="https://www.mql5.com/ru/articles/19589",
                title="Статистический анализ ценовых уровней",
                main_strategy_id=3,
                secondary_ids=[2],
                components_extracted=["statistical_levels", "distribution_shape_analysis"],
                branch_impact="Range(3) GROWING: skewness+kurtosis as regime indicators.",
                evolution_summary="Statistical level generation via mean/median/mode/stddev/percentiles. Distribution shape (skewness, kurtosis) as market state features. ATR-scaled dynamic thresholds.",
                processed_at="2026-05-13T14:06:00Z",
            ),
            ProcessedArticle(
                article_id=18361,
                url="https://www.mql5.com/ru/articles/18361",
                title="Гауссова копула и t-копула Стьюдента",
                main_strategy_id=6,
                secondary_ids=[7],
                components_extracted=["gaussian_copula", "student_t_copula", "tail_dependency_coefficients", "ecdf_marginals"],
                branch_impact="Statistical(6) ACCELERATING: elliptic copulas for tail risk quantification.",
                evolution_summary="Gaussian + Student-t copula implementations. ECDF for non-parametric marginals. Tail dependency coefficients quantify joint extreme events. Foundation for portfolio crash hedging.",
                processed_at="2026-05-13T14:07:00Z",
            ),
            ProcessedArticle(
                article_id=19077,
                url="https://www.mql5.com/ru/articles/19077",
                title="Торговля по линиям тренда (наименьшие квадраты)",
                main_strategy_id=1,
                secondary_ids=[3, 5],
                components_extracted=["least_squares_trendline", "swing_detection", "dynamic_sr_generation"],
                branch_impact="Trend(1) EVOLVING: algorithmic trendline construction replaces manual drawing.",
                evolution_summary="Least-squares regression for dynamic S/R lines from swing points. Angle constraints + penetration tolerance. Auto-execution on touch confirmation.",
                processed_at="2026-05-13T14:08:00Z",
            ),
            ProcessedArticle(
                article_id=18971,
                url="https://www.mql5.com/ru/articles/18971",
                title="Тестер стратегий для Python и MetaTrader 5",
                main_strategy_id=5,
                secondary_ids=[7],
                components_extracted=["python_trade_simulator", "margin_mode_engine", "sqlite_trade_history"],
                branch_impact="MultiInd(5) GROWING: Python backtesting infrastructure.",
                evolution_summary="Python TradeSimulator mirroring MT5 tester. Multi-margin-mode support (Forex/CFD/Futures). SQLite deal history. Foundation for Python-based strategy evolution.",
                processed_at="2026-05-13T14:09:00Z",
            ),
            ProcessedArticle(
                article_id=19460,
                url="https://www.mql5.com/ru/articles/19460",
                title="ДНК-профиль рынка",
                main_strategy_id=2,
                secondary_ids=[1, 3, 7],
                components_extracted=["market_dna_profiling", "cosine_distance_regime_shift", "fractal_cycle_analysis", "session_decomposition"],
                branch_impact="MeanRev(2) EVOLVING + instrument_dna STRENGTHENED. 17-metric genetic fingerprint per ticker.",
                evolution_summary="17-metric quantitative fingerprint: wick ratios, volatility clustering, fractal cycles, retracement distribution, session ranges. Cosine/L2 distance for mutation (regime shift) detection. Diagnostic layer, not signal generator.",
                processed_at="2026-05-13T14:10:00Z",
            ),
            ProcessedArticle(
                article_id=21507,
                url="https://www.mql5.com/ru/articles/21507",
                title="Статистический арбитраж: коинтеграция + DuckDB",
                main_strategy_id=6,
                secondary_ids=[2, 7],
                components_extracted=["cointegration_engine", "eigenvector_stability", "olap_analytics", "structural_break_detection"],
                branch_impact="Statistical(6) BREAKTHROUGH: full cointegration pipeline with real-time stability monitoring.",
                evolution_summary="Engle-Granger + Johansen cointegration. Rolling eigenvector comparison for weight stability. DuckDB OLAP 23x faster than SQLite. CUSUM + Chow structural break detection. Multi-asset basket arbitrage.",
                processed_at="2026-05-13T14:11:00Z",
            ),
            ProcessedArticle(
                article_id=19365,
                url="https://www.mql5.com/ru/articles/19365",
                title="Автоматизация BOS и ChOCh (структурные пробои)",
                main_strategy_id=4,
                secondary_ids=[1, 3],
                components_extracted=["structure_break_detector", "change_of_character", "fractal_pivot_engine", "closed_bar_confirmation"],
                branch_impact="Breakout(4) ACCELERATING: BOS+ChOCh as early/confirmed structure shift detection.",
                evolution_summary="Fractal-based pivot detection → ChOCh (early warning: failed higher high) + BOS (confirmation: decisive close beyond swing). Closed-bar-only logic prevents repainting. Pruning of aged fractals.",
                processed_at="2026-05-13T14:12:00Z",
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
