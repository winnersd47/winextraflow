"""Evolutionary Strategy Registry — tracks strategy branches, versions, and mutations.

Implements the EVOLUTIONARY QUANT ARCHITECTURE protocol:
- Each signal/strategy classified → extracts evolutionary patterns → evolves architecture
- Strategy branches have statuses: Stable → Growing → Evolving → Accelerating → Breakthrough
- Architecture tracks components detected across all signals
- Next evolution steps are computed automatically

This is the KNOWLEDGE ACCUMULATION CENTER of the platform.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from app.services.quant.regime import MarketRegime
from app.services.quant.strategy_classifier import StrategyID, STRATEGY_META

logger = logging.getLogger(__name__)


class BranchStatus(str, Enum):
    EXPERIMENTAL = "experimental"
    STABLE = "stable"
    GROWING = "growing"
    EVOLVING = "evolving"
    ACCELERATING = "accelerating"
    CORE_EVOLUTION = "core_evolution"
    BREAKTHROUGH = "breakthrough"


@dataclass
class EvolutionaryBranch:
    """A strategy evolutionary branch."""
    strategy_id: int
    name: str
    name_ru: str
    status: BranchStatus
    version: str  # e.g. "v1.2"
    signal_count: int = 0
    win_rate: float = 0.0
    avg_meta_score: float = 0.0
    detected_components: list[str] = field(default_factory=list)
    last_evolution: str = ""
    mutations: list[str] = field(default_factory=list)


@dataclass
class ArchitecturalComponent:
    """A detected architectural component across the system."""
    name: str
    description: str
    detected_in: list[int]  # Strategy IDs where detected
    strength: float  # 0.0 — 1.0
    status: str  # "active", "emerging", "planned"


# ═══════════════════════════════════════════════════════════
# EVOLUTIONARY REGISTRY — живое состояние системы
# ═══════════════════════════════════════════════════════════

class EvolutionaryRegistry:
    """Manages the evolutionary state of the entire architecture."""

    def __init__(self):
        self.branches: dict[int, EvolutionaryBranch] = {}
        self.components: dict[str, ArchitecturalComponent] = {}
        self.evolution_log: list[dict] = []
        self.architecture_version = "2.0.0"
        self._init_branches()
        self._init_components()

    def _init_branches(self):
        """Initialize all 7 strategy branches."""
        for sid in StrategyID:
            meta = STRATEGY_META.get(sid, {})
            self.branches[sid.value] = EvolutionaryBranch(
                strategy_id=sid.value,
                name=meta.get("name", f"Strategy {sid.value}"),
                name_ru=meta.get("name_ru", f"Стратегия {sid.value}"),
                status=BranchStatus.STABLE,
                version="v1.0",
            )

    def _init_components(self):
        """Initialize detected architectural components."""
        components = [
            ("regime_detection", "Market Regime Detection", "Определение режима рынка", [1, 2, 3, 4], 0.9, "active"),
            ("signal_confidence", "Signal Confidence Engine", "Движок уверенности сигнала (AI Rating)", [5, 7], 0.85, "active"),
            ("risk_reward_analysis", "Risk/Reward Analysis", "Анализ соотношения риск/прибыль", [1, 4], 0.8, "active"),
            ("provider_scoring", "Provider Historical Scoring", "Скоринг провайдеров по истории", [1, 2, 3, 4, 5, 6, 7], 0.9, "active"),
            ("dynamic_weighting", "Dynamic Weight Allocation", "Динамическое распределение весов по режиму", [7], 0.75, "active"),
            ("strategy_classification", "Auto Strategy Classification", "Автоклассификация сигналов в 7 типов", [1, 2, 3, 4, 5, 6, 7], 0.85, "active"),
            ("backtesting_engine", "Historical Backtesting", "Бэктестинг на исторических данных", [1, 2, 3, 4, 5], 0.9, "active"),
            ("execution_layer", "Multi-Exchange Execution", "Исполнение на 9 биржах", [1, 4, 7], 0.8, "active"),
            ("copy_trading", "Copy Trading Pipeline", "Копирование сделок по стратегиям", [1, 5, 7], 0.7, "active"),
            ("false_breakout_filter", "False Breakout Filter", "Фильтр ложных пробоев", [4], 0.3, "emerging"),
            ("pattern_probability", "Pattern Probability Engine", "Вероятностная оценка свечных паттернов (pin bar, engulfing, doji)", [2, 4, 5], 0.4, "emerging"),
            ("volume_confirmation", "Volume Confirmation Layer", "Volume-weighted валидация сигналов", [1, 4, 6], 0.35, "emerging"),
            ("instrument_dna", "Instrument DNA Profiler", "Уникальный профиль тикера по эффективности паттернов", [2, 3, 6], 0.3, "emerging"),
            ("liquidity_pressure", "Liquidity Pressure Score", "Оценка давления ликвидности", [6], 0.2, "planned"),
            ("uncertainty_estimation", "Uncertainty Estimation Engine", "Движок оценки неопределённости", [7], 0.3, "emerging"),
            ("transition_detector", "Regime Transition Detector", "Детектор перехода между режимами", [1, 2, 3, 4], 0.4, "emerging"),
            ("breakout_confirmation", "Breakout Confirmation Logic", "Подтверждение пробоя последующими барами", [4], 0.45, "emerging"),
            ("cellular_automaton", "Cellular Automaton Grid (10K agents)", "Клеточный автомат: 10000 ячеек-агентов с тороидальной топологией", [7, 1, 2, 3], 0.5, "emerging"),
            ("online_learning", "Online Learning Without Interruption", "Непрерывное обучение без остановки торговли", [7], 0.45, "emerging"),
            ("strategy_archetypes", "Strategy Archetype System", "10 архетипов стратегий (trend, reversion, consensus...)", [1, 2, 3, 5, 7], 0.5, "emerging"),
            ("network_health", "Network Health Metric", "% прибыльных агентов = здоровье системы", [7], 0.4, "emerging"),
            ("genome_mutation", "Genome Mutation Engine", "Эволюция параметров (SL, risk, grid-step, lot) по PnL", [7], 0.4, "emerging"),
            ("consensus_dynamics", "Consensus Dynamics", "Влияние соседей + подавление при высокой волатильности", [5, 7], 0.35, "emerging"),
            ("adaptive_allocation", "Adaptive Capital Allocation", "Адаптивное распределение капитала", [7], 0.25, "planned"),
            ("population_logic", "Strategy Population Competition", "Конкуренция популяции стратегий (cells compete)", [7], 0.35, "emerging"),
            # From #22474: ML Pipeline
            ("onnx_inference", "ONNX Model Inference", "LSTM→ONNX инференс в терминале без Python", [7], 0.45, "emerging"),
            ("feature_pipeline", "Feature Preprocessing Pipeline", "PCA + StandardScaler + matrix ops в MQL5", [7, 5], 0.5, "emerging"),
            # From #22562: GDformer
            ("learnable_memory", "Learnable Market Memory", "Обучаемый словарь Key-Value для сопоставления режимов", [7], 0.5, "emerging"),
            ("pattern_abstention", "Pattern Abstention Logic", "Отказ от сделки при отсутствии надёжного паттерна", [7, 5], 0.45, "emerging"),
            # From #19697 + #19589: Statistical levels
            ("statistical_levels", "Statistical S/R Levels", "Уровни из mean/median/mode/percentiles + Z-score", [2, 3], 0.55, "emerging"),
            ("kde_mode_estimation", "KDE Modal Estimation", "Ядерная оценка плотности для нахождения моды цены", [2, 3, 6], 0.4, "emerging"),
            # From #19931 + #18361: Copulas
            ("copula_dependency", "Copula Dependency Modeling", "Архимедовы + эллиптические копулы для зависимостей", [6], 0.55, "emerging"),
            ("tail_dependency_model", "Tail Dependency Coefficients", "Оценка совместных экстремальных событий", [6, 7], 0.5, "emerging"),
            # From #20020: Bitwise patterns
            ("bitwise_pattern_encoding", "Bitwise Pattern Encoding", "Побитовая кодировка комбинаций индикаторов", [5], 0.4, "emerging"),
            # From #19850: ML label fix
            ("label_uniqueness_weighting", "Label Uniqueness Weighting", "Взвешивание по уникальности для устранения IID-нарушения", [7], 0.6, "emerging"),
            ("purged_kfold", "Purged K-Fold CV", "Кросс-валидация с очисткой от утечек данных", [7], 0.55, "emerging"),
            # From #19460: Market DNA
            ("market_dna_profiling", "Market DNA Profiler", "17-метрический генетический отпечаток тикера", [2, 3, 7], 0.5, "emerging"),
            ("cosine_regime_shift", "Cosine Distance Regime Shift", "Детекция смены режима через косинусное расстояние", [1, 2, 3, 4], 0.45, "emerging"),
            # From #21507: Cointegration
            ("cointegration_engine", "Cointegration Testing Engine", "Engle-Granger + Johansen для парного трейдинга", [6], 0.55, "emerging"),
            ("structural_break_detection", "Structural Break Detection", "CUSUM + Chow тесты для обнаружения разломов", [6, 7], 0.45, "emerging"),
            # From #19365: BOS/ChOCh
            ("structure_break_detector", "BOS/ChOCh Structure Detector", "Break of Structure + Change of Character на фракталах", [4, 1], 0.5, "emerging"),
            # From #19077: Trendlines
            ("least_squares_trendline", "Algorithmic Trendline Engine", "Линии тренда через метод наименьших квадратов", [1, 3], 0.45, "emerging"),
            # Foundation layers (future)
            ("reinforcement_layer", "Reinforcement Learning Layer", "Слой обучения с подкреплением", [7], 0.15, "planned"),
            ("digital_twin", "Digital Twin Simulation", "Цифровой двойник рынка", [7], 0.1, "planned"),
        ]
        for name, desc_en, desc_ru, sids, strength, status in components:
            self.components[name] = ArchitecturalComponent(
                name=name, description=f"{desc_en} / {desc_ru}",
                detected_in=sids, strength=strength, status=status,
            )

    def record_signal_evolution(self, strategy_id: int, meta_score: float, regime: str, components_detected: list[str]):
        """Record an evolutionary event from a signal evaluation."""
        branch = self.branches.get(strategy_id)
        if not branch:
            return

        branch.signal_count += 1
        branch.avg_meta_score = (
            (branch.avg_meta_score * (branch.signal_count - 1) + meta_score) / branch.signal_count
        )

        # Update detected components
        for comp_name in components_detected:
            if comp_name not in branch.detected_components:
                branch.detected_components.append(comp_name)
            if comp_name in self.components:
                self.components[comp_name].strength = min(
                    self.components[comp_name].strength + 0.01, 1.0
                )

        # Evolve branch status based on signal count
        if branch.signal_count >= 100 and branch.avg_meta_score >= 0.7:
            branch.status = BranchStatus.ACCELERATING
            branch.version = "v3.0"
        elif branch.signal_count >= 50 and branch.avg_meta_score >= 0.5:
            branch.status = BranchStatus.EVOLVING
            branch.version = "v2.0"
        elif branch.signal_count >= 20:
            branch.status = BranchStatus.GROWING
            branch.version = "v1.5"

        branch.last_evolution = datetime.now(timezone.utc).isoformat()

        self.evolution_log.append({
            "timestamp": branch.last_evolution,
            "strategy_id": strategy_id,
            "meta_score": round(meta_score, 3),
            "regime": regime,
            "branch_status": branch.status.value,
        })

        # Keep log bounded
        if len(self.evolution_log) > 1000:
            self.evolution_log = self.evolution_log[-500:]

    def get_state(self) -> dict:
        """Full evolutionary state of the architecture."""
        active_components = [c for c in self.components.values() if c.status == "active"]
        emerging_components = [c for c in self.components.values() if c.status == "emerging"]
        planned_components = [c for c in self.components.values() if c.status == "planned"]

        return {
            "architecture_version": self.architecture_version,
            "total_signals_processed": sum(b.signal_count for b in self.branches.values()),
            "branches": [
                {
                    "strategy_id": b.strategy_id,
                    "name": b.name,
                    "name_ru": b.name_ru,
                    "status": b.status.value,
                    "version": b.version,
                    "signal_count": b.signal_count,
                    "avg_meta_score": round(b.avg_meta_score, 3),
                    "detected_components": b.detected_components,
                    "last_evolution": b.last_evolution,
                }
                for b in self.branches.values()
            ],
            "components": {
                "active": [{"name": c.name, "description": c.description, "strength": round(c.strength, 2)} for c in active_components],
                "emerging": [{"name": c.name, "description": c.description, "strength": round(c.strength, 2)} for c in emerging_components],
                "planned": [{"name": c.name, "description": c.description, "strength": round(c.strength, 2)} for c in planned_components],
            },
            "evolution_roadmap": {
                "v1": "Regime Detection + Strategy Mapping + Execution (DONE)",
                "v2": "Adaptive Scoring + AI Validation + Dynamic Weighting (CURRENT)",
                "v3": "False Breakout Filter + Regime Transition + Uncertainty Estimation (NEXT)",
                "v4": "Multi-Agent Competition + Reinforcement Learning + Adaptive Allocation",
                "v5": "Evolutionary Ecosystem + Digital Twin + Autonomous Intelligence",
            },
            "recent_evolution": self.evolution_log[-20:],
        }


# Singleton
evolutionary_registry = EvolutionaryRegistry()
