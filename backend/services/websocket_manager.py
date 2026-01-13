"""WebSocket Connection Manager for RFID Edge Service.

Manages WebSocket connections and broadcasts real-time events to connected clients.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

from database import get_tag_counts
from models import Decision

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and event broadcasting."""

    def __init__(self) -> None:
        """Initialize WebSocket manager with empty connection list."""
        self._connections: list[WebSocket] = []
        self._status_task: asyncio.Task[None] | None = None

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and track a new WebSocket connection.

        Args:
            websocket: The WebSocket connection to accept.
        """
        await websocket.accept()
        self._connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self._connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from tracking.

        Args:
            websocket: The WebSocket connection to remove.
        """
        if websocket in self._connections:
            self._connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Total connections: {len(self._connections)}")

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast a message to all connected clients.

        Args:
            message: Dictionary to serialize and send as JSON.
        """
        if not self._connections:
            return

        # Serialize datetime objects
        def json_serializer(obj: Any) -> str:
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        text = json.dumps(message, default=json_serializer)
        disconnected: list[WebSocket] = []

        for connection in self._connections:
            try:
                await connection.send_text(text)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                disconnected.append(connection)

        # Remove failed connections
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_tag_detected(
        self,
        tag_id: str,
        decision: Decision,
        rssi: float | None = None,
        antenna: int | None = None,
    ) -> None:
        """Broadcast a TAG_DETECTED event.

        Args:
            tag_id: RFID tag identifier.
            decision: PASS or ALARM decision.
            rssi: Signal strength.
            antenna: Antenna number.
        """
        await self.broadcast({
            "type": "TAG_DETECTED",
            "tag_id": tag_id,
            "rssi": rssi,
            "antenna": antenna,
            "decision": decision.value,
            "timestamp": datetime.now(timezone.utc),
        })

    async def broadcast_alarm_triggered(
        self,
        tag_id: str,
        gate_id: str,
        rssi: float | None = None,
    ) -> None:
        """Broadcast an ALARM_TRIGGERED event.

        Args:
            tag_id: RFID tag identifier.
            gate_id: Gate identifier.
            rssi: Signal strength.
        """
        await self.broadcast({
            "type": "ALARM_TRIGGERED",
            "tag_id": tag_id,
            "gate_id": gate_id,
            "rssi": rssi,
            "timestamp": datetime.now(timezone.utc),
        })

    async def broadcast_command_response(self, payload: dict[str, Any]) -> None:
        """Broadcast a COMMAND_RESPONSE event from the RFID reader.

        Args:
            payload: Command response payload from reader.
        """
        # Extract data from various response formats
        # Different commands return data in different fields:
        # - power command: {"power": {"ant1": 30, ...}}
        # - gpo command: {"gpo": {"gpo1": 1, ...}}
        # - rfid status: {"network": {...}, "system": {...}}
        data = (
            payload.get("data")
            or payload.get("power")
            or payload.get("gpo")
        )

        # For status response, include network and system info
        if payload.get("network") or payload.get("system"):
            data = {
                "network": payload.get("network"),
                "system": payload.get("system"),
            }

        await self.broadcast({
            "type": "COMMAND_RESPONSE",
            "command": payload.get("command"),
            "action": payload.get("action"),
            "status": payload.get("status"),
            "message": payload.get("message"),
            "data": data,
            "timestamp": datetime.now(timezone.utc),
        })

    async def broadcast_reader_status(self, payload: dict[str, Any]) -> None:
        """Broadcast a READER_STATUS event from the RFID reader.

        Args:
            payload: Reader status payload.
        """
        await self.broadcast({
            "type": "READER_STATUS",
            "status": payload.get("status"),
            "uptime": payload.get("uptime"),
            "memory": payload.get("memory"),
            "antennas": payload.get("antennas"),
            "network": payload.get("network"),
            "system": payload.get("system"),
            "timestamp": datetime.now(timezone.utc),
        })

    async def _status_update_loop(self, mqtt_connected_fn: Any) -> None:
        """Periodically broadcast status updates.

        Args:
            mqtt_connected_fn: Callable that returns MQTT connection status.
        """
        while True:
            try:
                await asyncio.sleep(5)
                if self._connections:
                    counts = await get_tag_counts()
                    await self.broadcast({
                        "type": "STATUS_UPDATE",
                        "mqtt_connected": mqtt_connected_fn(),
                        "in_cart_count": counts["in_cart_count"],
                        "paid_count": counts["paid_count"],
                    })
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in status update loop: {e}")
                await asyncio.sleep(5)

    def start_status_updates(self, mqtt_connected_fn: Any) -> None:
        """Start periodic status update broadcasts.

        Args:
            mqtt_connected_fn: Callable that returns MQTT connection status.
        """
        if self._status_task is None or self._status_task.done():
            self._status_task = asyncio.create_task(self._status_update_loop(mqtt_connected_fn))

    async def stop_status_updates(self) -> None:
        """Stop periodic status update broadcasts."""
        if self._status_task and not self._status_task.done():
            self._status_task.cancel()
            try:
                await self._status_task
            except asyncio.CancelledError:
                pass


# Global WebSocket manager instance
_ws_manager: WebSocketManager | None = None


def get_ws_manager() -> WebSocketManager:
    """Get WebSocket manager instance (singleton)."""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager()
    return _ws_manager

