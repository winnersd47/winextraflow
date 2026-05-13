"""Revenue tracking service — monitors annual income for tax compliance.

Russian tax law for self-employed (самозанятый / НПД):
- Federal Law No. 422-FZ "On experiment on professional income tax"
- Max annual income: 2,400,000 RUB
- Tax rate: 4% from individuals, 6% from legal entities
- No employees allowed
- Must register via "Мой налог" app

Progressive business stages:
1. Самозанятый (НПД): 0 — 2.4M RUB/year
2. ИП (УСН 6%): 2.4M — 150M RUB/year
3. ООО: 150M+ RUB/year or need for employees/licenses
"""

import logging
from datetime import datetime, timezone
from dataclasses import dataclass

from sqlalchemy import func, select, and_, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment, PaymentStatus

logger = logging.getLogger(__name__)

# Revenue thresholds (RUB)
SELF_EMPLOYED_LIMIT = 2_400_000   # Самозанятый max
IP_LIMIT = 150_000_000            # ИП УСН max
USD_TO_RUB = 90.0                 # Approximate exchange rate


@dataclass
class BusinessStage:
    key: str
    name_ru: str
    name_en: str
    max_revenue: int
    tax_rate: str
    description_ru: str
    description_en: str
    next_stage_ru: str
    next_stage_en: str


STAGES = [
    BusinessStage(
        key="self_employed",
        name_ru="Самозанятый (НПД)",
        name_en="Self-Employed (NPD)",
        max_revenue=SELF_EMPLOYED_LIMIT,
        tax_rate="4-6%",
        description_ru="Налог на профессиональный доход. ФЗ-422. Лимит 2.4 млн руб/год.",
        description_en="Professional income tax. FZ-422. Limit 2.4M RUB/year.",
        next_stage_ru="При превышении 2.4 млн руб → перейти на ИП (УСН 6%)",
        next_stage_en="When exceeding 2.4M RUB → switch to Individual Entrepreneur (USN 6%)",
    ),
    BusinessStage(
        key="ip",
        name_ru="ИП (УСН 6%)",
        name_en="Individual Entrepreneur (USN 6%)",
        max_revenue=IP_LIMIT,
        tax_rate="6%",
        description_ru="Упрощённая система налогообложения 'доходы'. Лимит 150 млн руб/год.",
        description_en="Simplified tax system 'income'. Limit 150M RUB/year.",
        next_stage_ru="При превышении 150 млн руб или найме сотрудников → перейти на ООО",
        next_stage_en="When exceeding 150M RUB or hiring employees → switch to LLC",
    ),
    BusinessStage(
        key="ooo",
        name_ru="ООО",
        name_en="LLC (OOO)",
        max_revenue=999_999_999_999,
        tax_rate="ОСНО / УСН",
        description_ru="Общество с ограниченной ответственностью. Без лимита дохода.",
        description_en="Limited Liability Company. No income limit.",
        next_stage_ru="Максимальный уровень для РФ. Рассмотрите международную экспансию.",
        next_stage_en="Maximum level for Russia. Consider international expansion.",
    ),
]


class RevenueService:
    """Tracks platform revenue and provides tax compliance alerts."""

    async def get_annual_revenue(self, db: AsyncSession, year: int | None = None) -> dict:
        """Calculate total completed revenue for a given year."""
        if year is None:
            year = datetime.now(timezone.utc).year

        result = await db.execute(
            select(
                func.coalesce(func.sum(Payment.amount), 0.0),
                func.count(),
            ).where(and_(
                Payment.status == PaymentStatus.COMPLETED,
                extract("year", Payment.created_at) == year,
            ))
        )
        row = result.one()
        total_usd = float(row[0])
        count = int(row[1])
        total_rub = total_usd * USD_TO_RUB

        # Monthly breakdown
        monthly_result = await db.execute(
            select(
                extract("month", Payment.created_at).label("month"),
                func.sum(Payment.amount),
                func.count(),
            ).where(and_(
                Payment.status == PaymentStatus.COMPLETED,
                extract("year", Payment.created_at) == year,
            )).group_by(extract("month", Payment.created_at))
            .order_by(extract("month", Payment.created_at))
        )
        monthly = [
            {"month": int(r[0]), "amount_usd": float(r[1]), "amount_rub": float(r[1]) * USD_TO_RUB, "count": int(r[2])}
            for r in monthly_result.all()
        ]

        return {
            "year": year,
            "total_usd": round(total_usd, 2),
            "total_rub": round(total_rub, 2),
            "transaction_count": count,
            "monthly": monthly,
            "usd_to_rub_rate": USD_TO_RUB,
        }

    def get_current_stage(self, annual_rub: float) -> BusinessStage:
        """Determine current business stage based on annual revenue."""
        for stage in STAGES:
            if annual_rub <= stage.max_revenue:
                return stage
        return STAGES[-1]

    def get_revenue_alerts(self, annual_rub: float) -> list[dict]:
        """Generate alerts based on revenue thresholds."""
        alerts = []
        stage = self.get_current_stage(annual_rub)

        pct = (annual_rub / stage.max_revenue * 100) if stage.max_revenue > 0 else 0

        if pct >= 90:
            alerts.append({
                "level": "critical",
                "title_ru": f"ПРЕВЫШЕНИЕ ЛИМИТА {stage.name_ru}",
                "title_en": f"APPROACHING {stage.name_en} LIMIT",
                "message_ru": f"Доход составляет {pct:.0f}% от лимита ({annual_rub:,.0f} / {stage.max_revenue:,.0f} руб). Необходимо срочно подготовить переход на следующую форму.",
                "message_en": f"Revenue at {pct:.0f}% of limit ({annual_rub:,.0f} / {stage.max_revenue:,.0f} RUB). Urgently prepare transition to next business form.",
                "action_ru": stage.next_stage_ru,
                "action_en": stage.next_stage_en,
            })
        elif pct >= 70:
            alerts.append({
                "level": "warning",
                "title_ru": f"Приближение к лимиту {stage.name_ru}",
                "title_en": f"Approaching {stage.name_en} limit",
                "message_ru": f"Доход составляет {pct:.0f}% от лимита ({annual_rub:,.0f} / {stage.max_revenue:,.0f} руб). Рекомендуется начать подготовку к переходу.",
                "message_en": f"Revenue at {pct:.0f}% of limit ({annual_rub:,.0f} / {stage.max_revenue:,.0f} RUB). Recommended to start preparing transition.",
                "action_ru": stage.next_stage_ru,
                "action_en": stage.next_stage_en,
            })
        elif pct >= 50:
            alerts.append({
                "level": "info",
                "title_ru": "Текущий статус дохода",
                "title_en": "Current revenue status",
                "message_ru": f"Доход: {annual_rub:,.0f} руб ({pct:.0f}% от лимита {stage.name_ru}).",
                "message_en": f"Revenue: {annual_rub:,.0f} RUB ({pct:.0f}% of {stage.name_en} limit).",
                "action_ru": "Продолжайте работу в текущем режиме.",
                "action_en": "Continue operating in current mode.",
            })

        # Tax reminder
        now = datetime.now(timezone.utc)
        if now.month == 12 or now.month == 1:
            tax_amount = annual_rub * 0.06  # Assume 6% worst case
            alerts.append({
                "level": "info",
                "title_ru": "Напоминание о налогах",
                "title_en": "Tax reminder",
                "message_ru": f"Приближается конец налогового периода. Ориентировочная сумма налога: {tax_amount:,.0f} руб.",
                "message_en": f"Tax period ending soon. Estimated tax amount: {tax_amount:,.0f} RUB.",
                "action_ru": "Проверьте отчётность в приложении 'Мой налог'.",
                "action_en": "Check your reports in the 'My Tax' app.",
            })

        return alerts

    async def get_full_report(self, db: AsyncSession) -> dict:
        """Full revenue report with stage and alerts."""
        revenue = await self.get_annual_revenue(db)
        annual_rub = revenue["total_rub"]
        stage = self.get_current_stage(annual_rub)
        alerts = self.get_revenue_alerts(annual_rub)

        pct = (annual_rub / stage.max_revenue * 100) if stage.max_revenue > 0 else 0

        return {
            "revenue": revenue,
            "stage": {
                "key": stage.key,
                "name_ru": stage.name_ru,
                "name_en": stage.name_en,
                "max_revenue_rub": stage.max_revenue,
                "tax_rate": stage.tax_rate,
                "description_ru": stage.description_ru,
                "description_en": stage.description_en,
                "usage_pct": round(pct, 1),
                "remaining_rub": round(stage.max_revenue - annual_rub, 2),
            },
            "alerts": alerts,
            "stages": [
                {
                    "key": s.key,
                    "name_ru": s.name_ru,
                    "name_en": s.name_en,
                    "max_revenue_rub": s.max_revenue,
                    "tax_rate": s.tax_rate,
                    "is_current": s.key == stage.key,
                }
                for s in STAGES
            ],
        }


revenue_service = RevenueService()
