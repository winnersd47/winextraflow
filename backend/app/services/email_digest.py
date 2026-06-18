"""Email Digest Service — weekly summary of best signals, market regime, new strategies.

In development mode, generates digest content but doesn't actually send emails.
For production, integrate with SendGrid / AWS SES / SMTP.
"""

import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal import Signal, SignalAction, SignalStatus
from app.models.provider import Provider
from app.models.user import User

logger = logging.getLogger(__name__)


class EmailDigestService:
    """Generates weekly email digest content."""

    async def generate_digest(self, db: AsyncSession) -> dict:
        """Generate digest data for the past week."""
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)

        # Signals this week
        signals = (await db.execute(
            select(Signal).where(Signal.created_at >= week_ago)
        )).scalars().all()

        total_signals = len(signals)
        buys = sum(1 for s in signals if s.action == SignalAction.BUY)
        sells = total_signals - buys

        # Top signals by confidence
        top_signals = sorted(
            [s for s in signals if s.ai_confidence],
            key=lambda s: s.ai_confidence or 0,
            reverse=True,
        )[:5]

        # Closed with profit
        closed = [s for s in signals if s.profit_pct is not None]
        profitable = [s for s in closed if s.profit_pct > 0]
        win_rate = len(profitable) / len(closed) if closed else 0

        # Best performers
        best = sorted(closed, key=lambda s: s.profit_pct or 0, reverse=True)[:3]

        # Top providers this week
        providers = (await db.execute(
            select(Provider)
            .where(Provider.win_rate.isnot(None))
            .order_by(Provider.win_rate.desc())
            .limit(3)
        )).scalars().all()

        # New users this week
        new_users = (await db.execute(
            select(func.count(User.id)).where(User.created_at >= week_ago)
        )).scalar() or 0

        # Market regime
        try:
            from app.services.quant.regime import regime_detector
            regime = regime_detector.detect_regime()
        except Exception:
            regime = {"regime": "unknown", "confidence": 0}

        return {
            "week_start": week_ago.strftime("%d.%m.%Y"),
            "week_end": datetime.now(timezone.utc).strftime("%d.%m.%Y"),
            "total_signals": total_signals,
            "buys": buys,
            "sells": sells,
            "win_rate": round(win_rate * 100),
            "closed_trades": len(closed),
            "regime": regime.get("regime", "unknown"),
            "regime_confidence": round(regime.get("confidence", 0) * 100),
            "new_users": new_users,
            "top_signals": [
                {
                    "ticker": s.ticker,
                    "action": s.action.value if hasattr(s.action, "value") else str(s.action),
                    "wef_score": round((s.ai_confidence or 0) * 100),
                    "entry_price": s.entry_price,
                }
                for s in top_signals
            ],
            "best_performers": [
                {
                    "ticker": s.ticker,
                    "profit_pct": round(s.profit_pct, 1),
                }
                for s in best
            ],
            "top_providers": [
                {
                    "name": p.name,
                    "win_rate": round((p.win_rate or 0) * 100),
                    "signals": p.total_signals,
                }
                for p in providers
            ],
        }

    def format_digest_text(self, data: dict) -> str:
        """Format digest as plain text (for Telegram/email)."""
        lines = [
            f"📊 WinExtraFlow — Еженедельный дайджест",
            f"📅 {data['week_start']} — {data['week_end']}",
            "",
            f"📈 Сигналов за неделю: {data['total_signals']} (BUY: {data['buys']}, SELL: {data['sells']})",
            f"🎯 Win Rate закрытых: {data['win_rate']}%",
            f"🌊 Режим рынка: {data['regime']} ({data['regime_confidence']}%)",
            f"👥 Новых пользователей: {data['new_users']}",
            "",
        ]

        if data["top_signals"]:
            lines.append("🏆 Топ сигналы по WEF Score:")
            for s in data["top_signals"]:
                lines.append(f"  • {s['ticker']} {s['action'].upper()} — WEF {s['wef_score']}%")

        if data["best_performers"]:
            lines.append("")
            lines.append("💰 Лучшие результаты:")
            for s in data["best_performers"]:
                lines.append(f"  • {s['ticker']} +{s['profit_pct']}%")

        if data["top_providers"]:
            lines.append("")
            lines.append("⭐ Топ провайдеры:")
            for p in data["top_providers"]:
                lines.append(f"  • {p['name']} — WR {p['win_rate']}% ({p['signals']} сигналов)")

        lines.extend([
            "",
            "⚠️ Не является инвестиционной рекомендацией.",
            "🔗 winextraflow.com",
        ])

        return "\n".join(lines)


email_digest_service = EmailDigestService()
