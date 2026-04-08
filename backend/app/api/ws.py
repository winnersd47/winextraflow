"""WebSocket endpoint for real-time signal broadcasting.

Clients connect to /api/v1/ws/signals and receive push notifications
whenever a new signal is created from any source.
"""

import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.models.signal import Signal
from app.services.signal_aggregator import signal_aggregator

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket) -> str:
        """Accept a new WebSocket connection and return its ID."""
        await websocket.accept()
        conn_id = str(uuid.uuid4())
        self.active_connections[conn_id] = websocket
        logger.info(f"WebSocket connected: {conn_id} (total: {len(self.active_connections)})")
        return conn_id

    def disconnect(self, conn_id: str):
        """Remove a WebSocket connection."""
        self.active_connections.pop(conn_id, None)
        logger.info(f"WebSocket disconnected: {conn_id} (total: {len(self.active_connections)})")

    async def broadcast(self, data: dict):
        """Send data to all connected clients."""
        disconnected = []
        message = json.dumps(data, default=str)
        for conn_id, ws in self.active_connections.items():
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(conn_id)

        for conn_id in disconnected:
            self.disconnect(conn_id)


manager = ConnectionManager()


async def _on_new_signal(signal: Signal):
    """Callback for signal_aggregator — broadcasts new signals to all WS clients."""
    data = {
        "type": "new_signal",
        "signal": {
            "id": str(signal.id),
            "ticker": signal.ticker,
            "action": signal.action.value,
            "entry_price": signal.entry_price,
            "take_profit": signal.take_profit,
            "stop_loss": signal.stop_loss,
            "timeframe": signal.timeframe,
            "ai_confidence": signal.ai_confidence,
            "created_at": signal.created_at.isoformat() if signal.created_at else None,
        },
    }
    await manager.broadcast(data)


# Register listener with the signal aggregator
signal_aggregator.on_new_signal(_on_new_signal)


@router.websocket("/signals")
async def websocket_signals(websocket: WebSocket):
    """WebSocket endpoint for real-time signal updates.

    Connect: ws://localhost:8000/api/v1/ws/signals
    Receives: JSON messages with type "new_signal"
    """
    conn_id = await manager.connect(websocket)
    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to WinExtraFlow signal feed",
        })

        # Keep connection alive, handle client messages
        while True:
            data = await websocket.receive_text()
            # Client can send ping/pong or filters in the future
            if data == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(conn_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(conn_id)
