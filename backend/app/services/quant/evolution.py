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
            # From batch 2 (#20327): Volume Profile
            ("volume_profile_engine", "Volume Profile Engine", "200-бинный профиль объёма: POC, VAH/VAL, HVN/LVN", [2, 3, 6], 0.55, "emerging"),
            ("market_memory_layer", "Market Memory Layer", "Институциональная память: объём как предиктивный фреймворк", [2, 3], 0.5, "emerging"),
            # From #20271: Bayesian indicator selection
            ("bayesian_ucb_optimizer", "Bayesian UCB Indicator Optimizer", "Байесовский multi-armed bandit для выбора индикаторов", [6, 7], 0.5, "emerging"),
            ("kendall_distance_corr", "Kendall+Distance Correlation", "Тау Кендалла + дистанционная корреляция для независимости", [6, 5], 0.45, "emerging"),
            # From #20287: Options Greeks
            ("delta_gamma_engine", "Delta/Gamma Hedging Engine", "Дельта-нейтральное хеджирование + гамма-скальпинг", [6], 0.4, "emerging"),
            # From #19290: Microstructure
            ("tick_microstructure", "Tick Microstructure Analysis", "Реконструкция потока ордеров из тиков (без стакана)", [5, 6], 0.5, "emerging"),
            ("vwap_engine", "Rolling VWAP Engine", "VWAP на тиковом буфере с кольцевым хранилищем", [5], 0.45, "emerging"),
            # From #22377: Markov features
            ("markov_chain_features", "Markov Chain Feature Preprocessor", "3-state Markov → transition matrix → 15 ML-фичей", [7], 0.5, "emerging"),
            ("entropy_signal_filter", "Shannon Entropy Signal Filter", "Фильтрация неопределённых сигналов через энтропию", [7, 5], 0.45, "emerging"),
            # From #22403: Bayesian regime
            ("bayesian_regime_detection", "Bayesian Adaptive Regime Detection", "Байесовский вывод с adaptive forgetting для нестационарных рынков", [7, 2], 0.55, "emerging"),
            ("change_point_detector", "Change-Point Detector", "Обнаружение точки смены режима за 17-20 наблюдений", [7, 1, 4], 0.5, "emerging"),
            # From #17518: Bimodal profile
            ("bimodal_profile", "Bimodal Market Profile", "Детекция мультикластерных сессий + дельта-профиль", [3, 2], 0.45, "emerging"),
            ("absorption_detector", "Absorption/Exhaustion Detector", "Обнаружение исчерпания: POC delta > 40% активности", [3, 4], 0.4, "emerging"),
            # From #22242: GPU compute
            ("gpu_pattern_engine", "GPU Pattern Matching Engine", "OpenCL параллельное сопоставление свечных паттернов", [7, 4], 0.4, "emerging"),
            ("monte_carlo_simulator", "Monte Carlo Trade Simulator", "Симуляция исходов сделок с worst-case моделированием", [7, 6], 0.45, "emerging"),
            # From #22390: Metaheuristic optimization
            ("metaheuristic_optimizer", "Metaheuristic Parameter Optimizer", "BOA/GA/PSO для оптимизации параметров стратегий", [7], 0.35, "emerging"),
            # From batch 3 (#22502/#22432/#22396): ReGEN-TAD Risk Assessment
            ("multi_circuit_risk", "Multi-Circuit Risk Verification", "3 параллельных выхода: прогноз + уточнение + реконструкция → несогласованность = риск", [7], 0.55, "emerging"),
            ("risk_tokenization", "Risk Tokenization Module", "Конвертация дивергенции Transformer↔LSTM в risk-token в пространстве решений", [7], 0.5, "emerging"),
            ("anomaly_ensemble_scoring", "6-Metric Anomaly Ensemble", "Реконструкция + прогноз + плотность + остатки + распределение + атрибуция", [7, 6], 0.5, "emerging"),
            ("confidence_divergence", "Confidence Divergence Detector", "Обнаружение моментов когда уверенность модели не соответствует реальности", [7], 0.55, "emerging"),
            # From #22230: LLM Meta-Prompting
            ("llm_signal_generator", "LLM Signal Generator", "Генерация BUY/SELL через Claude API с JSON-парсингом", [7], 0.45, "emerging"),
            ("meta_prompt_optimizer", "Self-Improving Prompt Optimizer", "Meta-LLM переписывает промпт из анализа ошибок = градиентный спуск в языке", [7], 0.5, "emerging"),
            # From #19576: Execution discipline
            ("atr_dynamic_trailing", "ATR Dynamic Trailing System", "Динамический трейлинг nLoss=a*ATR с сессионным фильтром", [1, 4], 0.5, "emerging"),
            ("execution_discipline", "Execution Discipline Engine", "Ежедневный лимит убытков + итеративная проверка маржи + паралич исполнения", [1, 5], 0.45, "emerging"),
            # From #19137: Sentiment
            ("sentiment_oscillator", "Multi-TF Sentiment Oscillator", "3-feature candle → multi-TF fusion → EMA smoothing → [-100,+100]", [5, 1], 0.45, "emerging"),
            # From #22383: Event architecture
            ("event_driven_bus", "Event-Driven Message Bus", "Индикаторы → custom events → агрегация → исполнение (decoupled)", [5, 7], 0.5, "emerging"),
            # From #22196: News filter
            ("economic_calendar_filter", "Economic Calendar Volatility Shield", "Фильтр новостей: снижение размера позиций перед NFP/CPI/GDP", [5, 1, 4], 0.4, "emerging"),
            # From Telegram channel "Трейдинг: Индикаторы и Стратегии" (347 messages)
            ("rsi_oscillator", "RSI Oscillator Engine", "Индекс относительной силы: перекупленность/перепроданность", [2, 5], 0.6, "emerging"),
            ("macd_histogram_engine", "MACD Histogram Analysis", "MACD: гистограмма + сигнальная линия + дивергенции", [1, 5], 0.55, "emerging"),
            ("bollinger_squeeze", "Bollinger Bands Squeeze Detector", "Сжатие/расширение полос Боллинджера = волатильность", [3, 4], 0.45, "emerging"),
            ("stochastic_zones", "Stochastic Zone Analysis", "Стохастик: зоны перекупленности/перепроданности + кроссовер", [2, 5], 0.5, "emerging"),
            ("ma_crossover_system", "Moving Average Crossover System", "Пересечение скользящих средних как трендовый фильтр", [1, 5], 0.6, "emerging"),
            ("sr_level_engine", "Support/Resistance Level Engine", "Автоопределение уровней поддержки и сопротивления", [2, 3], 0.65, "emerging"),
            ("divergence_scanner", "Multi-Indicator Divergence Scanner", "Поиск дивергенций RSI/MACD/Stochastic с ценой", [2, 4, 5], 0.55, "emerging"),
            ("candlestick_library", "Candlestick Pattern Library", "Библиотека свечных моделей (доджи, молот, поглощение...)", [2, 4, 5], 0.5, "emerging"),
            ("trend_rules_engine", "Trend Identification Rules", "Правила определения тренда (HH/HL, LH/LL, MA direction)", [1], 0.6, "emerging"),
            ("risk_rules_engine", "Risk Management Rules Engine", "Правила управления риском: стоп-лосс, размер позиции, дневной лимит", [1, 2, 3, 4, 5], 0.65, "emerging"),
            ("tp_logic_engine", "Take Profit Logic Engine", "Логика фиксации прибыли: трейлинг, частичное закрытие, R:R", [1, 4, 5], 0.55, "emerging"),
            ("volume_basics", "Volume Analysis Basics", "Базовый анализ объёмов: подтверждение тренда, кульминация", [1, 6], 0.5, "emerging"),
            ("news_filter", "News Trading Filter", "Фильтр новостей: календарь, импакт, стратегия на выход данных", [5, 4], 0.45, "emerging"),
            ("zigzag_structure", "ZigZag Structure Analyzer", "ZigZag: определение волн, swing points, структура рынка", [1, 3, 4], 0.45, "emerging"),
            ("fibonacci_retracement", "Fibonacci Retracement Levels", "Уровни Фибоначчи: 23.6%, 38.2%, 50%, 61.8%, 78.6%", [2, 3], 0.5, "emerging"),
            ("trading_psychology", "Trading Psychology Module", "Психология: дисциплина, контроль эмоций, FOMO/revenge trading", [1, 2, 3, 4, 5], 0.4, "emerging"),
            ("position_sizing_calc", "Position Sizing Calculator", "Калькулятор размера позиции от % риска и расстояния до SL", [1, 2, 3, 4, 5], 0.55, "emerging"),
            ("multi_tf_confirmation", "Multi-Timeframe Confirmation", "Подтверждение сигнала на старшем таймфрейме", [1, 5], 0.5, "emerging"),
            # From "Душевный трейдинг" (4903 messages) — MOEX-focused
            ("futures_basis_trading", "Futures Basis Trading", "Торговля базисом фьючерсов: контанго/бэквордация", [6], 0.55, "emerging"),
            ("options_strategies", "Options Strategies Engine", "Опционные стратегии: страйки, экспирация, колл/пут", [6], 0.5, "emerging"),
            ("moex_sector_rotation", "MOEX Sector Rotation", "Ротация секторов MOEX: перетоки между секторами", [6, 1], 0.45, "emerging"),
            ("dividend_strategy", "Dividend Gap Strategy", "Дивидендные стратегии: гэп, отсечка, восстановление", [2, 6], 0.55, "emerging"),
            ("oil_correlation_engine", "Oil Correlation Engine", "Корреляция нефти с RU акциями (Роснефть, Лукойл)", [6, 1], 0.5, "emerging"),
            ("gold_safe_haven_logic", "Gold Safe-Haven Logic", "Золото как убежище: переток при рисках", [6, 2], 0.45, "emerging"),
            ("bond_yield_analysis", "Bond Yield Analysis", "Анализ доходности ОФЗ: купон, дюрация, кривая", [6], 0.4, "emerging"),
            ("advanced_stop_loss", "Advanced Stop-Loss Techniques", "Продвинутые стопы: вынос, охота за стопами, защита", [1, 4, 5], 0.55, "emerging"),
            ("position_mgmt_advanced", "Advanced Position Management", "Доливка, усреднение, пирамидинг позиций", [1, 5], 0.5, "emerging"),
            ("morning_analysis_routine", "Morning Analysis Routine", "Утренний дайджест: обзор рынка перед сессией", [5], 0.45, "emerging"),
            ("intraday_moex_levels", "MOEX Intraday Levels", "Внутридневные уровни для MOEX акций и фьючерсов", [3, 4], 0.5, "emerging"),
            ("swing_trading_moex", "MOEX Swing Trading", "Среднесрочная торговля акциями MOEX (1-4 недели)", [1, 2], 0.5, "emerging"),
            ("earnings_reaction", "Earnings Reaction Trading", "Торговля на квартальной отчётности компаний", [4, 5], 0.4, "emerging"),
            ("market_sentiment_score", "Market Sentiment Score", "Индекс настроений рынка: страх/жадность", [5, 7], 0.45, "emerging"),
            ("risk_per_trade_rules", "Risk Per Trade Rules", "Правила риска на сделку: 1-2% от депозита", [1, 2, 3, 4, 5], 0.6, "emerging"),
            ("breakeven_trailing_adv", "Advanced Breakeven+Trailing", "Перевод в безубыток + адаптивный трейлинг", [1, 4], 0.5, "emerging"),
            ("gap_trading_moex", "MOEX Gap Trading", "Торговля гэпами на открытии MOEX", [4], 0.4, "emerging"),
            ("volume_confirm_moex", "MOEX Volume Confirmation", "Подтверждение пробоя объёмом на MOEX", [4, 5], 0.5, "emerging"),
            ("news_reaction_engine", "News Reaction Trading", "Реакция рынка на новости и макроданные", [5, 4], 0.45, "emerging"),
            # From update +959 msgs (AI, macro, rates)
            ("ai_trading_integration", "AI Trading Integration", "ИИ/ChatGPT в торговых решениях (552 упоминания в канале)", [7, 5], 0.6, "emerging"),
            ("cb_rate_analysis", "CB Rate Analysis", "Анализ ставки ЦБ и влияния на акции/облигации", [6, 5], 0.55, "emerging"),
            ("sanctions_filter", "Sanctions/Geopolitical Filter", "Фильтр санкционных рисков для MOEX", [6, 5], 0.45, "emerging"),
            ("ipo_strategy", "IPO Trading Strategy", "IPO: участие, аллокация, локап-период", [4, 5], 0.4, "emerging"),
            ("portfolio_rebalancing", "Portfolio Rebalancing", "Ребалансировка портфеля: целевые доли, триггеры", [6, 5], 0.45, "emerging"),
            ("long_short_bias", "Long/Short Bias Detection", "Long/short перекос рынка для направленных сделок", [1, 2], 0.5, "emerging"),
            ("macro_overlay", "Macro Fundamental Overlay", "Макро: ВВП, инфляция, PMI как фильтр стратегий", [5, 6], 0.5, "emerging"),
            ("currency_impact", "Currency Impact Model", "Влияние курса рубля на MOEX акции", [6, 1], 0.45, "emerging"),
            # From "РБК Крипто" channel (5000 messages, Feb 2018 — Jul 2020)
            # S1: Trend Following
            ("btc_dominance_regime", "BTC Dominance Regime Indicator", "BTC dominance >70% = risk-off, <55% = altseason / Доминация BTC как индикатор режима", [1, 6], 0.55, "emerging"),
            ("post_halving_cycle", "Post-Halving Cycle Pattern", "Исторический цикл роста после халвинга BTC (2012: +6000%, 2016: +2000%)", [1], 0.5, "emerging"),
            ("rising_wedge_detector", "Rising Wedge Pattern Detector", "Восходящий клин + падающий объём = медвежий сигнал", [1, 4], 0.45, "emerging"),
            ("golden_cross_signal", "Golden Cross MA Signal", "50-day MA пересекает 200-day MA вверх — предшествовало +170% росту", [1], 0.5, "emerging"),
            ("google_trends_exhaustion", "Google Trends Trend Exhaustion", "Падение поисковых запросов -75% = подтверждение медвежьего рынка", [1, 5], 0.4, "emerging"),
            ("trade_war_btc_hedge", "Trade War BTC Hedge Signal", "Обратная корреляция BTC с торговыми войнами US-China", [1, 5], 0.45, "emerging"),
            # S2: Mean Reversion
            ("fib_ema_support_zone", "Fibonacci + EMA Support Zone", "200 EMA/SMA + Fib 0.5 как зона поддержки для входа", [2, 3], 0.5, "emerging"),
            ("altcoin_lag_reversion", "Altcoin Lag Reversion", "Альты отстают от BTC → взрывной рост с лагом (mean reversion)", [2, 6], 0.45, "emerging"),
            ("mining_difficulty_reversal", "Mining Difficulty Reversal Signal", "Падение сложности -25% = капитуляция майнеров → предвестник разворота", [2, 4], 0.5, "emerging"),
            ("ico_selling_pressure", "ICO/Token Unlock Selling Pressure", "Измеримый навес предложения от ICO-проектов (2.9M ETH)", [2, 6], 0.45, "emerging"),
            # S3: Breakout / Momentum
            ("exchange_listing_pump", "Exchange Listing Momentum", "Листинг на Binance → +80-202% за 1-4 часа → sell the spike", [3, 4], 0.5, "emerging"),
            ("ieo_launch_momentum", "IEO Launch Momentum", "IEO на Launchpad: +300-3950% post-listing (Binance 2019)", [3, 4], 0.45, "emerging"),
            ("psychological_level_break", "Psychological Level Breakout", "Пробой $10K/$5K с подтверждением объёмом = ускорение", [3], 0.5, "emerging"),
            ("new_pair_first_trade", "New Pair First Trade Scalp", "Первые сделки новых пар на бирже +30-110% выше рынка", [3, 7], 0.4, "emerging"),
            ("partnership_news_fade", "Partnership News Fade", "Buy the rumor, sell the news на партнёрствах (Ripple pattern)", [3, 5], 0.4, "emerging"),
            # S4: Statistical Arbitrage
            ("fake_volume_filter", "Fake Volume Detection Filter", "95% объёмов на нерег. биржах фейковые (Bitwise) — фильтр", [4, 7], 0.55, "emerging"),
            ("tether_depeg_risk", "Tether/Stablecoin Depeg Risk", "Отслеживание депега стейблкоинов как risk signal", [4, 6], 0.5, "emerging"),
            ("ponzi_liquidation_tracker", "Ponzi Liquidation Flow Tracker", "Отслеживание Whale Alert при ликвидации Ponzi-схем (PlusToken)", [4, 5], 0.45, "emerging"),
            ("options_expiry_vol", "Options Expiry Volatility", "Экспирация опционов ($1B+ BTC) → всплеск волатильности", [4, 6], 0.45, "emerging"),
            # S5: Sentiment / News
            ("regulatory_price_impact", "Regulatory News Price Impact", "Матрица чувствительности: Китай = макс, Катар = 0 импакт", [5], 0.55, "emerging"),
            ("death_count_contrarian", "Bitcoin Death Count Contrarian", "300+ «смертей» BTC = контрарный индикатор покупки", [5, 2], 0.45, "emerging"),
            ("vix_btc_lag_correlation", "VIX-BTC 30-Day Lag Correlation", "VIX коррелирует с BTC с 30-дневным лагом", [5, 6], 0.5, "emerging"),
            ("btc_gold_crisis_divergence", "BTC vs Gold Crisis Divergence", "BTC = risk-asset краткосрочно, но +145% в recovery vs gold", [5, 6], 0.5, "emerging"),
            ("sp500_btc_correlation", "S&P 500-BTC Correlation Regime", "Растущая корреляция S&P500/BTC = BTC как risk asset", [5, 1], 0.5, "emerging"),
            ("whale_wallet_tracker", "Whale Wallet Movement Tracker", "94K BTC в одной транзакции — CryptoQuant алерт → дамп", [5, 7], 0.55, "emerging"),
            ("local_premium_detector", "Local FX Crisis Premium Detector", "Премия BTC на локальных биржах при обвале валюты (Аргентина)", [5, 4], 0.35, "emerging"),
            # S6: Portfolio / Risk Management
            ("ema200_stop_loss", "200 EMA Stop-Loss Level", "Стоп-лосс на уровне 200 EMA ($8,350 Bitfinex, март 2018)", [6, 1], 0.5, "emerging"),
            ("btc_denominated_pnl", "BTC-Denominated P&L Framework", "Считать прибыль в BTC, не в fiat — фиксация от $15K+", [6], 0.4, "emerging"),
            ("institutional_futures_demand", "Institutional Futures Demand Signal", "Bakkt deliverable futures = реальный спрос на спот BTC", [6, 5], 0.45, "emerging"),
            ("mining_cost_floor", "Mining Cost Price Floor Model", "Стоимость майнинга ($1,800) = динамический пол цены BTC", [6], 0.5, "emerging"),
            ("hashrate_price_predictor", "Hashrate-Based Price Predictor", "Модель Capriole: hashrate + эффективность → $100K к 2025", [6, 1], 0.45, "emerging"),
            ("altcoin_rotation_signal", "Altcoin Rotation Signal", "BNB +145%, LTC +96%, BTC +12% → ротация из BTC в alts", [6, 3], 0.45, "emerging"),
            ("exchange_hack_risk", "Exchange Hack Systemic Risk", "Биржевые взломы как системный риск (Binance, Coinbene, Cashaa)", [6], 0.5, "emerging"),
            # S7: Market Making / Execution
            ("wash_trading_filter", "Wash Trading Detection", "Фильтр wash-trading: только CME/Coinbase/Kraken/Bitstamp надёжны", [7, 4], 0.5, "emerging"),
            ("flash_loan_attack_shield", "Flash Loan Attack Shield", "Защита от манипуляции оракулов через flash loans (bZx)", [7, 6], 0.45, "emerging"),
            # Macro factors
            ("covid_impact_chain", "COVID Impact Chain Model", "Цепочка: локдаун → майнинг стоп → sell-off → recovery +145%", [5, 6], 0.45, "emerging"),
            ("fed_dollar_weakness", "Fed/Dollar Weakness → BTC", "Печатание денег ФРС = фундаментальный драйвер BTC спроса", [5, 1], 0.5, "emerging"),
            ("stablecoin_ecosystem", "Stablecoin Ecosystem Signal", "Запуск новых стейблкоинов → рост ликвидности рынка", [3, 6], 0.4, "emerging"),
            # ═══ Batch 4: 50 new sources (MQL5 2025-2026 + research papers + trading communities) ═══

            # From #20935: Spatially-Controlled Aggregation
            ("spatial_event_aggregation", "Spatial Event Aggregation", "Пространственно-управляемая агрегация рыночных событий в multi-scale окне", [7, 5], 0.5, "emerging"),
            # From #20960: Perturbed State Space Models
            ("perturbed_ssm", "Perturbed State Space Model", "Модель пространства состояний с возмущениями: глобальная динамика + локальные микроизменения", [7, 1], 0.55, "emerging"),
            # From #22782: Uncertainty Assessment (UncAD)
            ("uncertainty_quantification", "Uncertainty Quantification Engine", "Энкодер неопределённости + распределение рыночных состояний для принятия решений", [7, 6], 0.55, "emerging"),
            # From #21792: Stacked Target-to-History Cross Attention
            ("stca_long_sequence", "STCA Long Sequence Analyzer", "Stacked Target-to-History Cross Attention для длинных рыночных последовательностей", [7, 1], 0.5, "emerging"),
            # From #21681: Unified Feature-Context Architecture
            ("unified_feature_context", "Unified Feature-Context Architecture", "Единая архитектура взаимодействия признаков и торгового контекста", [7, 5], 0.5, "emerging"),
            # From #22344: Robust Pattern Discovery
            ("robust_pattern_discovery", "Robust Pattern Discovery", "Поиск устойчивых закономерностей в разнородных рыночных данных ($100→$210)", [7, 4], 0.55, "emerging"),
            # From #21509: Scalable Structural Decomposition
            ("structural_decomposition", "Structural Feature Decomposition", "Масштабируемые трансформеры со структурной декомпозицией признаков", [7, 1], 0.5, "emerging"),
            # From #22711: UncAD Trading Decisions
            ("uncad_decision_engine", "UncAD Decision Engine", "Принятие торговых решений с адаптивным порогом неопределённости", [7, 6], 0.55, "emerging"),
            # From #21840: Adaptive Representation Scaling
            ("adaptive_repr_scaling", "Adaptive Representation Scaling", "ADS: адаптивное масштабирование представлений под волатильность рынка", [7, 1, 2], 0.5, "emerging"),
            # From #20799: Market Microstructure Diff-Modeling
            ("diff_microstructure", "Differential Microstructure Model", "Разностное моделирование рыночной микроструктуры: тик → ордер-флоу", [5, 7], 0.5, "emerging"),

            # From #22677: RSI Divergence Grid + Risk Manager
            ("rsi_grid_risk_manager", "RSI Grid + Risk Manager", "Сеточная стратегия с фильтром дивергенции RSI + лимит уровней + независимый риск-менеджер", [2, 6], 0.55, "emerging"),
            # From #22548: Hurst Exponent R/S Analysis
            ("hurst_exponent_indicator", "Hurst Exponent R/S Indicator", "Показатель Хёрста через R/S-анализ: персистентный vs антиперсистентный режим → выбор стратегии", [1, 2, 7], 0.6, "emerging"),
            # From #22745: Categorical Hidden Markov Model
            ("categorical_hmm", "Categorical Hidden Markov Model", "Категориальная скрытая марковская модель для прогноза дискретных рыночных состояний", [7, 1], 0.5, "emerging"),
            # From #22606: GDformer Global Dictionary
            ("gdformer_global_dict", "GDformer Global Dictionary", "Глобальный словарь паттернов + многоголовое кросс-внимание для финансовых рядов (OpenCL)", [7, 4], 0.55, "emerging"),
            # From #22502: Risk Assessment by Inconsistency
            ("inconsistency_risk", "Representation Inconsistency Risk", "Оценка риска по несогласованности представлений: 3 параллельных выхода модели", [7, 6], 0.5, "emerging"),
            # From #22395: MetaTrader 5 Debug + EX5 Protection
            ("mt5_debug_protection", "MT5 Debug & Protection Pipeline", "Пошаговая отладка → тестирование → защита EX5 в одной среде", [7], 0.35, "emerging"),
            # From #22391: Custom Symbols (Renko/Range/Volume)
            ("custom_symbol_engine", "Custom Symbol Engine", "Renko/Range/Volume бары + синтетические символы + стресс-тесты на пользовательских символах", [3, 4, 7], 0.45, "emerging"),
            # From #22211: Cellular Automaton Grid EA
            ("cellular_grid_ea", "Cellular Automaton Grid EA", "Сеточный советник на клеточном автомате с онлайн-обучением", [7, 2], 0.5, "emerging"),

            # From #19704: Options Without Options (Complex Strategies)
            ("synthetic_options", "Synthetic Options Engine", "Эмуляция опционных стратегий через базовые активы: straddle, strangle, butterfly", [6, 4], 0.5, "emerging"),
            # From #22674: 29-Pair Portfolio + L1 + VaR
            ("l1_var_portfolio", "L1-Filter + VaR Portfolio", "29-парный портфель с L1 фильтром тренда и VaR-распределением лотов", [6, 7], 0.6, "emerging"),
            # From #16960: Volatility Forecast via Python
            ("volatility_forecast_py", "Python Volatility Forecaster", "Прогноз волатильности через GARCH/EGARCH в Python → сигнал в MQL5", [6, 7], 0.5, "emerging"),
            # From #18681: 3D Bar Custom Symbol
            ("3d_bar_analysis", "3D Bar Analysis", "3D-бары: цена × время × объём × волатильность в одном символе", [3, 5], 0.4, "emerging"),
            # From #16719: 3D Trend Strength Indicator
            ("3d_trend_strength", "3D Trend Strength Indicator", "Индикатор силы и направления тренда на основе 3D-баров", [1, 3], 0.4, "emerging"),

            # From research: Transformer-based trading
            ("temporal_fusion_transformer", "Temporal Fusion Transformer", "TFT: multi-horizon прогноз с attention + variable selection для трейдинга", [7, 1], 0.5, "emerging"),
            ("patch_tst", "PatchTST Time Series", "Patch Time Series Transformer: сегментация ряда в патчи → channel-independent attention", [7, 1], 0.45, "emerging"),
            ("informer_sparse_attention", "Informer Sparse Attention", "ProbSparse attention для O(L log L) прогноза длинных последовательностей", [7], 0.45, "emerging"),
            ("autoformer_decomp", "Autoformer Decomposition", "Авто-корреляция + сезонно-трендовая декомпозиция внутри transformer", [7, 1], 0.45, "emerging"),
            ("fedformer_freq", "FEDformer Frequency", "Frequency Enhanced Decomposed Transformer: Fourier/Wavelet mixing в attention", [7, 1], 0.45, "emerging"),

            # From trading communities: practical strategies
            ("ichimoku_cloud", "Ichimoku Cloud Strategy", "Облако Ишимоку: Tenkan/Kijun cross + Chikou + Kumo twist для трендов", [1, 5], 0.5, "emerging"),
            ("harmonic_patterns", "Harmonic Pattern Detector", "Гармонические паттерны: Gartley, Butterfly, Bat, Crab, Shark с автодетекцией", [4, 2], 0.5, "emerging"),
            ("order_block_detector", "Order Block Detector", "Smart Money Concepts: Order Blocks + Fair Value Gaps + Liquidity Sweeps", [4, 3], 0.5, "emerging"),
            ("wyckoff_phases", "Wyckoff Phase Analyzer", "Анализ фаз Вайкоффа: Accumulation → Markup → Distribution → Markdown", [1, 2, 3], 0.5, "emerging"),
            ("elliot_wave_counter", "Elliott Wave Counter", "Подсчёт волн Эллиотта: импульс (1-5) + коррекция (A-B-C) автоматически", [1, 4], 0.45, "emerging"),
            ("supply_demand_zones", "Supply/Demand Zone Detector", "Автоопределение зон спроса/предложения по кластерам объёма", [2, 3, 6], 0.55, "emerging"),
            ("session_filter", "Trading Session Filter", "Фильтр по торговым сессиям: Asia, London, NY, overlap zones", [5, 7], 0.45, "emerging"),
            ("correlation_matrix", "Dynamic Correlation Matrix", "Динамическая матрица корреляций между тикерами: rolling window + heatmap", [6, 4], 0.5, "emerging"),
            ("mean_reversion_bands", "Mean Reversion Bands", "Keltner + Bollinger + Donchian каналы: тройное подтверждение для mean reversion", [2, 3], 0.5, "emerging"),
            ("momentum_divergence", "Multi-TF Momentum Divergence", "Дивергенция моментума на 3 таймфреймах: RSI + MACD + Stochastic совпадение", [2, 4, 5], 0.55, "emerging"),

            # From quantitative finance research
            ("garch_regime_switch", "GARCH Regime Switching", "Переключение между GARCH моделями волатильности по скрытым состояниям", [6, 7], 0.5, "emerging"),
            ("kalman_filter_price", "Kalman Filter Price Tracker", "Фильтр Кальмана для динамического отслеживания справедливой цены", [2, 7], 0.5, "emerging"),
            ("hawkes_process", "Hawkes Process Event Clustering", "Самовозбуждающийся процесс Хоукса для кластеризации рыночных событий", [5, 7], 0.45, "emerging"),
            ("pca_factor_model", "PCA Factor Model", "Факторная модель через PCA: выделение 3-5 главных драйверов рынка", [6, 7], 0.5, "emerging"),
            ("var_cvar_risk", "VaR/CVaR Risk Engine", "Value at Risk + Conditional VaR для оценки хвостовых рисков портфеля", [6], 0.55, "emerging"),
            ("sharpe_sortino_calmar", "Risk-Adjusted Return Suite", "Комплекс метрик: Sharpe + Sortino + Calmar + Omega ratio для сравнения стратегий", [6, 7], 0.55, "emerging"),
            ("walk_forward_optimizer", "Walk-Forward Optimizer", "Walk-Forward оптимизация: train/test окна → параметры обновляются периодически", [7], 0.5, "emerging"),
            ("regime_aware_sizing", "Regime-Aware Position Sizing", "Размер позиции зависит от текущего режима рынка: тренд=больше, боковик=меньше", [6, 1, 2], 0.55, "emerging"),

            # Foundation layers (future → closer)
            ("reinforcement_layer", "Reinforcement Learning Layer", "Слой обучения с подкреплением", [7], 0.25, "planned"),
            ("digital_twin", "Digital Twin Simulation", "Цифровой двойник рынка", [7], 0.15, "planned"),
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
