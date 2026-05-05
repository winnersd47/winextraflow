"""Capacity monitor — tracks system metrics and generates scaling alerts.

Monitors user count, signal volume, DB size and provides threshold-based
recommendations for infrastructure scaling.
"""

import logging
import os
import platform
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import psutil
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.signal import Signal
from app.models.order import Order

logger = logging.getLogger(__name__)


@dataclass
class CapacityThreshold:
    """Defines a scaling threshold with recommendation."""
    name: str
    max_users: int
    max_signals_per_day: int
    recommended_cpu: int
    recommended_ram_gb: int
    recommended_action: str
    monthly_cost_usd: int


# Scaling tiers
TIERS = [
    CapacityThreshold(
        name="starter",
        max_users=1_000,
        max_signals_per_day=5_000,
        recommended_cpu=1,
        recommended_ram_gb=1,
        recommended_action="Current setup is sufficient",
        monthly_cost_usd=10,
    ),
    CapacityThreshold(
        name="growth",
        max_users=5_000,
        max_signals_per_day=25_000,
        recommended_cpu=2,
        recommended_ram_gb=4,
        recommended_action="Add second app server + dedicated PostgreSQL",
        monthly_cost_usd=50,
    ),
    CapacityThreshold(
        name="scale",
        max_users=25_000,
        max_signals_per_day=100_000,
        recommended_cpu=4,
        recommended_ram_gb=8,
        recommended_action="Load balancer + 2 app servers + DB replicas + Redis cluster",
        monthly_cost_usd=200,
    ),
    CapacityThreshold(
        name="enterprise",
        max_users=100_000,
        max_signals_per_day=500_000,
        recommended_cpu=8,
        recommended_ram_gb=32,
        recommended_action="Kubernetes cluster + managed DB + CDN + dedicated workers",
        monthly_cost_usd=1000,
    ),
    CapacityThreshold(
        name="mega",
        max_users=1_000_000,
        max_signals_per_day=5_000_000,
        recommended_cpu=16,
        recommended_ram_gb=64,
        recommended_action="Multi-region deployment + sharding + auto-scaling",
        monthly_cost_usd=5000,
    ),
]


@dataclass
class CapacityAlert:
    level: str  # "info", "warning", "critical"
    title: str
    message: str
    current_tier: str
    next_tier: str | None
    action_required: str
    metrics: dict


class CapacityMonitor:
    """Monitors system capacity and generates scaling alerts."""

    async def get_metrics(self, db: AsyncSession) -> dict:
        """Collect current system metrics."""
        # User count
        total_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0

        # Signals today
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
        signals_today = (await db.execute(
            select(func.count()).select_from(Signal).where(Signal.created_at >= today_start)
        )).scalar() or 0

        # Total signals
        total_signals = (await db.execute(select(func.count()).select_from(Signal))).scalar() or 0

        # Orders today
        orders_today = (await db.execute(
            select(func.count()).select_from(Order).where(Order.created_at >= today_start)
        )).scalar() or 0

        # System resources
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/") if platform.system() != "Windows" else psutil.disk_usage("C:\\")

        return {
            "users": {
                "total": total_users,
            },
            "signals": {
                "total": total_signals,
                "today": signals_today,
            },
            "orders": {
                "today": orders_today,
            },
            "system": {
                "cpu_percent": round(cpu_percent, 1),
                "ram_total_gb": round(memory.total / (1024**3), 1),
                "ram_used_gb": round(memory.used / (1024**3), 1),
                "ram_percent": memory.percent,
                "disk_total_gb": round(disk.total / (1024**3), 1),
                "disk_used_gb": round(disk.used / (1024**3), 1),
                "disk_percent": round(disk.percent, 1),
            },
        }

    def get_current_tier(self, total_users: int) -> CapacityThreshold:
        """Determine which tier the current user count falls into."""
        for tier in TIERS:
            if total_users <= tier.max_users:
                return tier
        return TIERS[-1]

    def get_next_tier(self, total_users: int) -> CapacityThreshold | None:
        """Get the next scaling tier."""
        for i, tier in enumerate(TIERS):
            if total_users <= tier.max_users:
                return TIERS[i + 1] if i + 1 < len(TIERS) else None
        return None

    async def check_capacity(self, db: AsyncSession) -> CapacityAlert | None:
        """Check if scaling is needed and return alert if so."""
        metrics = await self.get_metrics(db)
        total_users = metrics["users"]["total"]
        current_tier = self.get_current_tier(total_users)
        next_tier = self.get_next_tier(total_users)

        # Calculate usage percentage within current tier
        usage_pct = (total_users / current_tier.max_users) * 100

        # CPU/RAM alerts
        cpu_critical = metrics["system"]["cpu_percent"] > 85
        ram_critical = metrics["system"]["ram_percent"] > 85

        # Determine alert level
        if usage_pct > 90 or cpu_critical or ram_critical:
            level = "critical"
            title = "SCALING REQUIRED"
            message = (
                f"System at {usage_pct:.0f}% capacity ({total_users:,} users). "
                f"CPU: {metrics['system']['cpu_percent']}%, RAM: {metrics['system']['ram_percent']}%. "
                f"Immediate action required to prevent degradation."
            )
        elif usage_pct > 70:
            level = "warning"
            title = "Approaching capacity limit"
            message = (
                f"System at {usage_pct:.0f}% capacity ({total_users:,} users). "
                f"Plan scaling to next tier soon."
            )
        elif usage_pct > 50:
            level = "info"
            title = "Capacity check"
            message = f"System at {usage_pct:.0f}% capacity ({total_users:,} users). Running normally."
        else:
            return None  # No alert needed

        return CapacityAlert(
            level=level,
            title=title,
            message=message,
            current_tier=current_tier.name,
            next_tier=next_tier.name if next_tier else None,
            action_required=next_tier.recommended_action if next_tier and usage_pct > 70 else current_tier.recommended_action,
            metrics=metrics,
        )

    async def get_full_report(self, db: AsyncSession) -> dict:
        """Full capacity report for admin dashboard."""
        metrics = await self.get_metrics(db)
        total_users = metrics["users"]["total"]
        current_tier = self.get_current_tier(total_users)
        next_tier = self.get_next_tier(total_users)
        alert = await self.check_capacity(db)

        return {
            "metrics": metrics,
            "current_tier": {
                "name": current_tier.name,
                "max_users": current_tier.max_users,
                "max_signals_per_day": current_tier.max_signals_per_day,
                "recommended_cpu": current_tier.recommended_cpu,
                "recommended_ram_gb": current_tier.recommended_ram_gb,
                "monthly_cost_usd": current_tier.monthly_cost_usd,
            },
            "next_tier": {
                "name": next_tier.name,
                "max_users": next_tier.max_users,
                "recommended_cpu": next_tier.recommended_cpu,
                "recommended_ram_gb": next_tier.recommended_ram_gb,
                "action": next_tier.recommended_action,
                "monthly_cost_usd": next_tier.monthly_cost_usd,
            } if next_tier else None,
            "usage_percent": round((total_users / current_tier.max_users) * 100, 1),
            "alert": {
                "level": alert.level,
                "title": alert.title,
                "message": alert.message,
                "action_required": alert.action_required,
            } if alert else None,
            "tiers": [
                {
                    "name": t.name,
                    "max_users": t.max_users,
                    "cpu": t.recommended_cpu,
                    "ram_gb": t.recommended_ram_gb,
                    "cost_usd": t.monthly_cost_usd,
                    "is_current": t.name == current_tier.name,
                }
                for t in TIERS
            ],
        }


capacity_monitor = CapacityMonitor()
