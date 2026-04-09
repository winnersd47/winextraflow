"""Copy Trading service — auto-executes signals for strategy subscribers.

Listens to new signals via signal_aggregator, resolves which strategy
the signal belongs to, finds subscribers with auto_execute enabled,
and places orders on their exchange accounts.
"""

import logging

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.copy_trade import CopyTrade, CopyTradeStatus
from app.models.exchange_account import ExchangeAccount
from app.models.order import OrderStatus
from app.models.signal import Signal
from app.models.strategy import Strategy
from app.models.subscription import Subscription, SubscriptionStatus
from app.services.execution import execution_service

logger = logging.getLogger(__name__)


class CopyTradingService:
    """Orchestrates copy trading: signal → subscribers → execution."""

    async def on_new_signal(self, signal: Signal):
        """Callback for signal_aggregator — triggered on every new signal.

        Flow:
        1. Find strategy linked to signal's provider
        2. Get active subscribers with auto_execute=True
        3. For each subscriber: find active exchange account → execute
        4. Track as CopyTrade record
        """
        try:
            async with async_session() as db:
                # 1. Find strategy for this provider
                result = await db.execute(
                    select(Strategy).where(
                        and_(
                            Strategy.provider_id == signal.provider_id,
                            Strategy.is_published == True,
                        )
                    )
                )
                strategy = result.scalar_one_or_none()
                if not strategy:
                    return  # No strategy for this provider, skip

                # 2. Get subscribers with auto_execute
                result = await db.execute(
                    select(Subscription).where(
                        and_(
                            Subscription.strategy_id == strategy.id,
                            Subscription.status == SubscriptionStatus.ACTIVE,
                            Subscription.auto_execute == True,
                        )
                    )
                )
                subscriptions = result.scalars().all()

                if not subscriptions:
                    return

                logger.info(
                    f"Copy trading: signal {signal.ticker} {signal.action.value} "
                    f"→ {len(subscriptions)} auto-execute subscribers"
                )

                # 3. Execute for each subscriber
                for sub in subscriptions:
                    await self._execute_for_subscriber(db, signal, strategy, sub)

        except Exception as e:
            logger.error(f"Copy trading error: {e}", exc_info=True)

    async def _execute_for_subscriber(
        self, db: AsyncSession, signal: Signal, strategy: Strategy, sub: Subscription
    ):
        """Execute a signal for a single subscriber."""
        try:
            # Find subscriber's active exchange account
            result = await db.execute(
                select(ExchangeAccount).where(
                    and_(
                        ExchangeAccount.user_id == sub.user_id,
                        ExchangeAccount.is_active == True,
                        ExchangeAccount.auto_execute == True,
                    )
                )
            )
            account = result.scalars().first()

            if not account:
                # No active auto-execute account, skip
                copy_trade = CopyTrade(
                    subscriber_id=sub.user_id,
                    strategy_id=strategy.id,
                    signal_id=signal.id,
                    status=CopyTradeStatus.SKIPPED,
                    error_message="No active auto-execute exchange account",
                )
                db.add(copy_trade)
                await db.commit()
                return

            # Execute signal
            order = await execution_service.execute_signal(
                db,
                signal=signal,
                account=account,
                user_id=sub.user_id,
            )

            # Track copy trade
            copy_trade = CopyTrade(
                subscriber_id=sub.user_id,
                strategy_id=strategy.id,
                signal_id=signal.id,
                order_id=order.id,
                status=(
                    CopyTradeStatus.EXECUTED
                    if order.status in (OrderStatus.FILLED, OrderStatus.PENDING)
                    else CopyTradeStatus.FAILED
                ),
                error_message=order.error_message,
            )
            db.add(copy_trade)
            await db.commit()

            logger.info(
                f"Copy trade: user {sub.user_id} → {order.status.value} "
                f"{signal.ticker} on {account.exchange.value}"
            )

        except Exception as e:
            logger.error(f"Copy trade failed for user {sub.user_id}: {e}")
            copy_trade = CopyTrade(
                subscriber_id=sub.user_id,
                strategy_id=strategy.id,
                signal_id=signal.id,
                status=CopyTradeStatus.FAILED,
                error_message=str(e)[:500],
            )
            db.add(copy_trade)
            await db.commit()


copy_trading_service = CopyTradingService()
