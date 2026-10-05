"""Execution service — orchestrates signal execution on exchanges.

Handles: exchange adapter selection, encryption of API keys,
risk management checks, order creation and tracking.
"""

import base64
import logging
import uuid

from cryptography.fernet import Fernet
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.exchange_account import ExchangeAccount, ExchangeName
from app.models.order import Order, OrderSide, OrderStatus, OrderType
from app.models.signal import Signal, SignalAction
from app.services.exchanges.base import BaseExchangeAdapter, OrderResult
from app.services.exchanges.demo import DemoAdapter
from app.services.exchanges.binance import BinanceAdapter
from app.services.exchanges.bybit import BybitAdapter
from app.services.exchanges.okx import OKXAdapter
from app.services.exchanges.kraken import KrakenAdapter
from app.services.exchanges.metatrader5 import MetaTrader5Adapter
from app.services.exchanges.interactive_brokers import InteractiveBrokersAdapter
from app.services.exchanges.tinkoff import TinkoffAdapter
from app.services.exchanges.exante import ExanteAdapter

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    """Derive a Fernet key from the dedicated encryption key."""
    import hashlib
    key = settings.encryption_key.encode()
    derived = hashlib.sha256(key).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_value(value: str) -> str:
    """Encrypt a string value using Fernet."""
    f = _get_fernet()
    return f.encrypt(value.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    """Decrypt a Fernet-encrypted string."""
    f = _get_fernet()
    return f.decrypt(encrypted.encode()).decode()


def _get_adapter(account: ExchangeAccount) -> BaseExchangeAdapter:
    """Get the appropriate exchange adapter for an account."""
    api_key = decrypt_value(account.api_key_encrypted)
    api_secret = decrypt_value(account.api_secret_encrypted)

    adapters = {
        ExchangeName.DEMO: DemoAdapter,
        # Crypto
        ExchangeName.BINANCE: BinanceAdapter,
        ExchangeName.BYBIT: BybitAdapter,
        ExchangeName.OKX: OKXAdapter,
        ExchangeName.KRAKEN: KrakenAdapter,
        # Forex / CFD
        ExchangeName.METATRADER5: MetaTrader5Adapter,
        ExchangeName.INTERACTIVE_BROKERS: InteractiveBrokersAdapter,
        # Stocks & Multi-asset
        ExchangeName.TINKOFF: TinkoffAdapter,
        ExchangeName.EXANTE: ExanteAdapter,
    }
    adapter_cls = adapters.get(account.exchange, DemoAdapter)
    # Adapters that have a testnet take the account's flag; the rest ignore it.
    # getattr, not account.is_testnet, so a row predating the column still works.
    testnet = bool(getattr(account, "is_testnet", True))
    try:
        return adapter_cls(api_key, api_secret, testnet=testnet)
    except TypeError:
        if testnet:
            # Refusing is the safe direction: an adapter with no testnet would
            # otherwise be handed live keys by an account marked as virtual.
            logger.warning(
                f"{account.exchange.value} has no testnet mode but account "
                f"'{account.label}' is marked testnet — using demo adapter instead"
            )
            return DemoAdapter(api_key, api_secret)
        return adapter_cls(api_key, api_secret)


class ExecutionService:
    """Executes trading signals on exchanges with risk management."""

    async def execute_signal(
        self,
        db: AsyncSession,
        *,
        signal: Signal,
        account: ExchangeAccount,
        user_id: uuid.UUID,
        order_type: OrderType = OrderType.MARKET,
        quantity: float | None = None,
    ) -> Order:
        """Execute a signal on the given exchange account.

        1. Risk checks
        2. Calculate quantity if not provided
        3. Place order via exchange adapter
        4. Save Order record
        """
        adapter = _get_adapter(account)

        # Risk check: AI confidence threshold
        if signal.ai_confidence is not None and signal.ai_confidence < account.min_confidence:
            return await self._create_failed_order(
                db, user_id=user_id, signal=signal, account=account,
                error=f"AI confidence {signal.ai_confidence:.2f} below threshold {account.min_confidence}",
            )

        # Risk check: daily loss limit
        if settings.execution_daily_loss_limit > 0:
            daily_loss = await self._get_daily_loss(db, user_id, account.id)
            if daily_loss >= settings.execution_daily_loss_limit:
                return await self._create_failed_order(
                    db, user_id=user_id, signal=signal, account=account,
                    error=f"Daily loss limit reached: ${daily_loss:.2f}",
                )

        # Calculate quantity from position size %
        if quantity is None:
            try:
                balance = await adapter.get_balance()
                position_value = balance * (account.max_position_pct / 100)
                price = await adapter.get_ticker_price(signal.ticker)
                if price > 0:
                    quantity = round(position_value / price, 6)
                else:
                    quantity = 0.0
            except Exception as e:
                logger.error(f"Quantity calculation error for signal {signal.id}: {e}")
                return await self._create_failed_order(
                    db, user_id=user_id, signal=signal, account=account,
                    error="Failed to calculate order quantity",
                )

        if quantity <= 0:
            return await self._create_failed_order(
                db, user_id=user_id, signal=signal, account=account,
                error="Calculated quantity is zero or negative",
            )

        # Map signal action to order side
        side = OrderSide.BUY if signal.action == SignalAction.BUY else OrderSide.SELL

        # Place order
        try:
            if order_type == OrderType.MARKET:
                result = await adapter.place_market_order(signal.ticker, side.value, quantity)
            else:
                result = await adapter.place_limit_order(
                    signal.ticker, side.value, quantity, signal.entry_price
                )
        except Exception as e:
            logger.error(f"Exchange error for signal {signal.id}: {e}")
            return await self._create_failed_order(
                db, user_id=user_id, signal=signal, account=account,
                error="Exchange order execution failed",
            )

        # Create Order record
        order = Order(
            user_id=user_id,
            signal_id=signal.id,
            exchange_account_id=account.id,
            exchange_order_id=result.exchange_order_id,
            exchange=account.exchange.value,
            symbol=signal.ticker,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=result.price,
            filled_price=result.filled_price,
            filled_quantity=result.filled_quantity,
            status=OrderStatus(result.status) if result.status in OrderStatus.__members__.values() else OrderStatus.PENDING,
            error_message=result.error,
        )
        db.add(order)
        await db.commit()
        await db.refresh(order)

        logger.info(
            f"Order {order.id}: {side.value} {quantity} {signal.ticker} "
            f"on {account.exchange.value} -> {order.status.value}"
        )
        return order

    async def _create_failed_order(
        self, db: AsyncSession, *, user_id, signal, account, error: str
    ) -> Order:
        """Create a failed order record for tracking."""
        order = Order(
            user_id=user_id,
            signal_id=signal.id,
            exchange_account_id=account.id,
            exchange=account.exchange.value,
            symbol=signal.ticker,
            side=OrderSide.BUY if signal.action == SignalAction.BUY else OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=0,
            status=OrderStatus.FAILED,
            error_message=error,
        )
        db.add(order)
        await db.commit()
        await db.refresh(order)
        logger.warning(f"Order failed for signal {signal.id}: {error}")
        return order

    async def _get_daily_loss(
        self, db: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID
    ) -> float:
        """Calculate total loss from filled orders today."""
        from datetime import datetime, timezone, timedelta
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
        result = await db.execute(
            select(func.coalesce(func.sum(Order.filled_price * Order.filled_quantity), 0.0)).where(
                and_(
                    Order.user_id == user_id,
                    Order.exchange_account_id == account_id,
                    Order.status == OrderStatus.FILLED,
                    Order.side == OrderSide.SELL,
                    Order.created_at >= today_start,
                )
            )
        )
        return abs(result.scalar() or 0.0)


execution_service = ExecutionService()
