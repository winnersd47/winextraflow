"""Architecture Level Readiness Monitor — tracks prerequisites for L3/L4 transitions.

Monitors real metrics and generates alerts when the platform is ready
to advance to the next architecture level.

L2 → L3 Prerequisites:
  - 10,000+ evaluated signals with outcomes (TP/SL)
  - 50+ paying users
  - 3+ months of stable L2 operation
  - Feedback loop accuracy > 60% (Meta Agent predictions match outcomes)
  - Revenue covers GPU server ($200-500/mo)

L3 → L4 Prerequisites:
  - 100,000+ signals with feedback
  - Revenue > 1M RUB/year (ИП status)
  - L3 running 6+ months with positive PnL
  - Team: 1+ ML engineer
  - Legal: готовность к лицензированию
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal import Signal, SignalStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import User
from app.models.order import Order, OrderStatus

logger = logging.getLogger(__name__)


@dataclass
class ReadinessMetric:
    """A single readiness prerequisite."""
    key: str
    name_ru: str
    name_en: str
    target: float
    current: float
    unit: str
    met: bool
    hint_ru: str
    hint_en: str


@dataclass
class FeedbackRecord:
    """Tracks how well Meta Agent predictions match real outcomes."""
    signal_id: str
    predicted_quality: float  # Meta Agent score at time of signal
    actual_outcome: str       # "tp_hit", "sl_hit", "expired"
    was_correct: bool         # quality > 0.5 and tp_hit, or quality < 0.5 and sl_hit


class ReadinessMonitor:
    """Monitors prerequisites for L3 and L4 architecture transitions."""

    def __init__(self):
        self.feedback_log: list[FeedbackRecord] = []

    def record_feedback(self, signal_id: str, predicted_quality: float, actual_outcome: str):
        """Record a feedback event — signal resolved, compare to prediction."""
        was_correct = (
            (predicted_quality >= 0.5 and actual_outcome == "tp_hit")
            or (predicted_quality < 0.5 and actual_outcome in ("sl_hit", "expired"))
        )
        self.feedback_log.append(FeedbackRecord(
            signal_id=signal_id,
            predicted_quality=predicted_quality,
            actual_outcome=actual_outcome,
            was_correct=was_correct,
        ))
        # Keep bounded
        if len(self.feedback_log) > 50000:
            self.feedback_log = self.feedback_log[-25000:]

    def get_feedback_accuracy(self) -> float:
        """Calculate feedback loop accuracy."""
        if not self.feedback_log:
            return 0.0
        correct = sum(1 for f in self.feedback_log if f.was_correct)
        return correct / len(self.feedback_log)

    async def check_l3_readiness(self, db: AsyncSession) -> dict:
        """Check all L3 prerequisites and return readiness report."""
        now = datetime.now(timezone.utc)

        # 1. Evaluated signals with outcomes (closed TP or SL)
        closed_count = (await db.execute(
            select(func.count()).select_from(Signal).where(
                Signal.status.in_([SignalStatus.CLOSED_TP, SignalStatus.CLOSED_SL])
            )
        )).scalar() or 0

        # 2. Total signals
        total_signals = (await db.execute(
            select(func.count()).select_from(Signal)
        )).scalar() or 0

        # 3. Active users (logged in = has orders or recent activity)
        total_users = (await db.execute(
            select(func.count()).select_from(User).where(User.is_active == True)
        )).scalar() or 0

        # 4. Paying users (completed payments)
        paying_users = (await db.execute(
            select(func.count(func.distinct(Payment.user_id))).where(
                Payment.status == PaymentStatus.COMPLETED
            )
        )).scalar() or 0

        # 5. Revenue this year
        from sqlalchemy import extract
        year = now.year
        annual_revenue = (await db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0.0)).where(and_(
                Payment.status == PaymentStatus.COMPLETED,
                extract("year", Payment.created_at) == year,
            ))
        )).scalar() or 0.0

        # 6. Filled orders (execution working)
        filled_orders = (await db.execute(
            select(func.count()).select_from(Order).where(Order.status == OrderStatus.FILLED)
        )).scalar() or 0

        # 7. Feedback accuracy
        fb_accuracy = self.get_feedback_accuracy()
        fb_count = len(self.feedback_log)

        # 8. Platform age (first signal date)
        first_signal = (await db.execute(
            select(Signal.created_at).order_by(Signal.created_at).limit(1)
        )).scalar()
        if first_signal:
            fs = first_signal if first_signal.tzinfo else first_signal.replace(tzinfo=timezone.utc)
            platform_days = (now - fs).days
        else:
            platform_days = 0

        # ─── L3 Metrics ──────────────────────────────────────
        l3_metrics = [
            ReadinessMetric(
                key="closed_signals", name_ru="Сигналов с результатом (TP/SL)",
                name_en="Signals with outcome (TP/SL)",
                target=10000, current=closed_count, unit="",
                met=closed_count >= 10000,
                hint_ru="Нужно 10 000 закрытых сигналов для обучения RL-агентов",
                hint_en="Need 10,000 closed signals to train RL agents",
            ),
            ReadinessMetric(
                key="paying_users", name_ru="Платящих пользователей",
                name_en="Paying users",
                target=50, current=paying_users, unit="",
                met=paying_users >= 50,
                hint_ru="Доход от 50 подписчиков покроет GPU-сервер для обучения",
                hint_en="Revenue from 50 subscribers covers GPU training server",
            ),
            ReadinessMetric(
                key="platform_age", name_ru="Дней стабильной работы L2",
                name_en="Days of stable L2 operation",
                target=90, current=platform_days, unit="дней",
                met=platform_days >= 90,
                hint_ru="3 месяца непрерывной работы для статистической значимости",
                hint_en="3 months continuous operation for statistical significance",
            ),
            ReadinessMetric(
                key="feedback_accuracy", name_ru="Точность Feedback Loop",
                name_en="Feedback loop accuracy",
                target=60, current=round(fb_accuracy * 100, 1), unit="%",
                met=fb_accuracy >= 0.6,
                hint_ru=f"Meta Agent правильно предсказал исход {fb_count} сигналов" if fb_count > 0 else "Ещё нет данных обратной связи. Сигналы должны закрыться (TP/SL).",
                hint_en=f"Meta Agent correctly predicted {fb_count} signal outcomes" if fb_count > 0 else "No feedback data yet. Signals need to close (TP/SL).",
            ),
            ReadinessMetric(
                key="monthly_revenue", name_ru="Месячный доход (для GPU сервера)",
                name_en="Monthly revenue (for GPU server)",
                target=200, current=round(annual_revenue / max(1, now.month), 2), unit="USD",
                met=(annual_revenue / max(1, now.month)) >= 200,
                hint_ru="$200+/мес покрывает RTX 4090 GPU VPS для обучения моделей",
                hint_en="$200+/mo covers RTX 4090 GPU VPS for model training",
            ),
            ReadinessMetric(
                key="execution_proven", name_ru="Исполненных ордеров",
                name_en="Executed orders",
                target=100, current=filled_orders, unit="",
                met=filled_orders >= 100,
                hint_ru="100+ ордеров подтверждают работоспособность execution pipeline",
                hint_en="100+ orders confirm execution pipeline works",
            ),
        ]

        l3_met = sum(1 for m in l3_metrics if m.met)
        l3_total = len(l3_metrics)
        l3_pct = round(l3_met / l3_total * 100)
        l3_ready = l3_met == l3_total

        # ─── L4 Metrics ──────────────────────────────────────
        l4_metrics = [
            ReadinessMetric(
                key="total_signals_100k", name_ru="Всего сигналов с feedback",
                name_en="Total signals with feedback",
                target=100000, current=total_signals, unit="",
                met=total_signals >= 100000,
                hint_ru="100K+ сигналов для evolutionary ecosystem",
                hint_en="100K+ signals for evolutionary ecosystem",
            ),
            ReadinessMetric(
                key="annual_revenue_1m", name_ru="Годовой доход > 1M руб (ИП)",
                name_en="Annual revenue > 1M RUB (IE status)",
                target=1000000, current=round(annual_revenue * 90), unit="RUB",
                met=(annual_revenue * 90) >= 1000000,
                hint_ru="Переход на ИП обязателен. Нужна команда.",
                hint_en="Individual Entrepreneur status required. Need a team.",
            ),
            ReadinessMetric(
                key="l3_months", name_ru="Месяцев работы L3 с прибылью",
                name_en="Months of profitable L3 operation",
                target=6, current=0, unit="мес",
                met=False,
                hint_ru="L3 должен работать 6+ месяцев с положительным PnL",
                hint_en="L3 must run 6+ months with positive PnL",
            ),
            ReadinessMetric(
                key="team_size", name_ru="ML-инженеров в команде",
                name_en="ML engineers on team",
                target=1, current=0, unit="",
                met=False,
                hint_ru="Минимум 1 ML-инженер для поддержки RL-агентов",
                hint_en="At least 1 ML engineer to maintain RL agents",
            ),
            ReadinessMetric(
                key="legal_readiness", name_ru="Юридическая готовность",
                name_en="Legal readiness",
                target=1, current=0, unit="",
                met=False,
                hint_ru="Лицензия ЦБ или CySEC для автономной торговли",
                hint_en="CB license or CySEC for autonomous trading",
            ),
        ]

        l4_met = sum(1 for m in l4_metrics if m.met)
        l4_total = len(l4_metrics)
        l4_pct = round(l4_met / l4_total * 100)

        # ─── Alerts ──────────────────────────────────────────
        alerts = []

        if l3_ready:
            alerts.append({
                "level": "success",
                "title_ru": "ГОТОВНОСТЬ К L3: Multi-Agent Decision + Reinforcement Learning",
                "title_en": "READY FOR L3: Multi-Agent Decision + Reinforcement Learning",
                "message_ru": "Все предварительные условия выполнены. Платформа готова к внедрению RL-агентов и мультиагентного принятия решений.",
                "message_en": "All prerequisites met. Platform ready for RL agents and multi-agent decision system.",
                "action_ru": "Начните с DQN-агента на закрытых сигналах: 'стоило ли входить в сделку?'",
                "action_en": "Start with a DQN agent on closed signals: 'was this trade worth entering?'",
            })
        elif l3_pct >= 60:
            alerts.append({
                "level": "info",
                "title_ru": f"Приближение к L3 ({l3_pct}%)",
                "title_en": f"Approaching L3 ({l3_pct}%)",
                "message_ru": f"Выполнено {l3_met}/{l3_total} условий. Продолжайте накопление данных и рост пользовательской базы.",
                "message_en": f"Met {l3_met}/{l3_total} conditions. Continue data accumulation and user base growth.",
                "action_ru": "Фокус на: " + ", ".join(m.name_ru for m in l3_metrics if not m.met),
                "action_en": "Focus on: " + ", ".join(m.name_en for m in l3_metrics if not m.met),
            })

        return {
            "current_level": 2,
            "l3": {
                "ready": l3_ready,
                "progress_pct": l3_pct,
                "met": l3_met,
                "total": l3_total,
                "metrics": [
                    {
                        "key": m.key,
                        "name_ru": m.name_ru,
                        "name_en": m.name_en,
                        "target": m.target,
                        "current": m.current,
                        "unit": m.unit,
                        "met": m.met,
                        "progress_pct": round(min(100, (m.current / m.target * 100)) if m.target > 0 else 0),
                        "hint_ru": m.hint_ru,
                        "hint_en": m.hint_en,
                    }
                    for m in l3_metrics
                ],
            },
            "l4": {
                "ready": l4_met == l4_total,
                "progress_pct": l4_pct,
                "met": l4_met,
                "total": l4_total,
                "metrics": [
                    {
                        "key": m.key,
                        "name_ru": m.name_ru,
                        "name_en": m.name_en,
                        "target": m.target,
                        "current": m.current,
                        "unit": m.unit,
                        "met": m.met,
                        "progress_pct": round(min(100, (m.current / m.target * 100)) if m.target > 0 else 0),
                        "hint_ru": m.hint_ru,
                        "hint_en": m.hint_en,
                    }
                    for m in l4_metrics
                ],
            },
            "alerts": alerts,
            "feedback_stats": {
                "total_records": fb_count,
                "accuracy_pct": round(fb_accuracy * 100, 1),
                "correct": sum(1 for f in self.feedback_log if f.was_correct),
                "incorrect": sum(1 for f in self.feedback_log if not f.was_correct),
            },
        }


readiness_monitor = ReadinessMonitor()
