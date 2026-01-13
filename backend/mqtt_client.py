"""MQTT Client for RFID Edge Service.

Handles communication with RFID gate readers via MQTT protocol.
"""

import asyncio
import json
import logging
import ssl
import time
from typing import Any, Callable, Optional

import paho.mqtt.client as mqtt

from config import get_config
from models import Decision
from services.decision import get_decision_engine
from services.websocket_manager import get_ws_manager

logger = logging.getLogger(__name__)


class MqttClient:
    """MQTT client for gate reader communication."""

    def __init__(self) -> None:
        """Initialize MQTT client."""
        self._client: Optional[mqtt.Client] = None
        self._connected = False
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 60.0
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._last_tag_seen: float = 0
        self._last_response: Optional[dict[str, Any]] = None
        self._last_reader_status: Optional[dict[str, Any]] = None

    @property
    def is_connected(self) -> bool:
        """Check if client is connected to broker."""
        return self._connected

    @property
    def last_tag_seen_seconds(self) -> Optional[int]:
        """Get seconds since last tag was seen."""
        if self._last_tag_seen == 0:
            return None
        return int(time.time() - self._last_tag_seen)

    @property
    def last_response(self) -> Optional[dict[str, Any]]:
        """Get the last command response received from reader."""
        return self._last_response

    @property
    def last_reader_status(self) -> Optional[dict[str, Any]]:
        """Get the last reader status received."""
        return self._last_reader_status

    def _get_topic(self, template: str) -> str:
        """Resolve topic template with client_id."""
        config = get_config()
        return template.replace("{client_id}", config.gate.client_id)

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: Optional[mqtt.Properties] = None,
    ) -> None:
        """Handle MQTT connection established."""
        if reason_code.value == 0:
            self._connected = True
            self._reconnect_delay = 1.0
            logger.info("MQTT connected to broker")

            config = get_config()
            # Subscribe to tag stream
            topic_tag = self._get_topic(config.gate.topic_tag_stream)
            logger.debug(f"[SUB] Subscribing to tag stream: topic={topic_tag}, qos=1")
            client.subscribe(topic_tag, qos=1)
            logger.info(f"[SUB] Subscribed to: {topic_tag}")

            # Subscribe to command responses
            topic_response = self._get_topic(config.gate.topic_data_response)
            logger.debug(f"[SUB] Subscribing to command response: topic={topic_response}, qos=1")
            client.subscribe(topic_response, qos=1)
            logger.info(f"[SUB] Subscribed to: {topic_response}")

            # Subscribe to reader status
            topic_status = self._get_topic(config.gate.topic_data_status)
            logger.debug(f"[SUB] Subscribing to reader status: topic={topic_status}, qos=1")
            client.subscribe(topic_status, qos=1)
            logger.info(f"[SUB] Subscribed to: {topic_status}")

            # Auto-start inventory scan on connect
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._auto_start_scan(),
                    self._loop,
                )
        else:
            logger.error(f"MQTT connection failed: {reason_code}")

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        disconnect_flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: Optional[mqtt.Properties] = None,
    ) -> None:
        """Handle MQTT disconnection."""
        self._connected = False
        logger.warning(f"MQTT disconnected: {reason_code} (value={reason_code.value}, name={reason_code.getName()})")

    def _on_subscribe(
        self,
        client: mqtt.Client,
        userdata: Any,
        mid: int,
        reason_code_list: list[mqtt.ReasonCode],
        properties: Optional[mqtt.Properties] = None,
    ) -> None:
        """Handle MQTT subscription confirmation."""
        for i, rc in enumerate(reason_code_list):
            if rc.is_failure:
                logger.error(f"[SUB] Subscription FAILED: mid={mid}, reason={rc}")
            else:
                logger.info(f"[SUB] Subscription CONFIRMED: mid={mid}, granted_qos={rc.value}")

    def _on_message(
        self,
        client: mqtt.Client,
        userdata: Any,
        message: mqtt.MQTTMessage,
    ) -> None:
        """Handle incoming MQTT message."""
        # Log at INFO level so it's always visible
        logger.info(f"[MSG-IN] >>> Received: topic={message.topic}, size={len(message.payload)} bytes")
        try:
            raw_payload = message.payload.decode("utf-8")
            payload = json.loads(raw_payload)
            logger.debug(
                f"[MSG-IN] Received message: topic={message.topic}, "
                f"qos={message.qos}, retain={message.retain}, "
                f"payload_size={len(raw_payload)} bytes"
            )
            logger.info(f"[MSG-IN] Payload: {raw_payload[:500]}")

            # Handle tag stream message
            if "stream/tag" in message.topic:
                self._last_tag_seen = time.time()
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._handle_tag_detection(payload),
                        self._loop,
                    )
            # Handle command response message
            elif "data/response" in message.topic:
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._handle_command_response(payload),
                        self._loop,
                    )
            # Handle reader status message
            elif "data/status" in message.topic:
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._handle_reader_status(payload),
                        self._loop,
                    )
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in MQTT message: {e}")
        except Exception as e:
            logger.error(f"Error handling MQTT message: {e}", exc_info=True)

    async def _handle_command_response(self, payload: dict[str, Any]) -> None:
        """Process command response from gate reader.

        Args:
            payload: Response payload with command result.
        """
        self._last_response = payload
        command = payload.get("command", "unknown")
        action = payload.get("action", "unknown")
        status = payload.get("status", "unknown")
        message = payload.get("message", "")

        logger.info(f"Command response: {command}/{action} -> {status}: {message}")

        # Broadcast to WebSocket clients
        ws_manager = get_ws_manager()

        # Handle rfid/status response as READER_STATUS event
        if command == "rfid" and action == "status":
            # Extract system info for reader status
            system_info = payload.get("system", {})
            await ws_manager.broadcast_reader_status({
                "status": "online" if status == "success" else "offline",
                "uptime": system_info.get("uptime", 0),
                "memory": system_info.get("free_heap", 0),
                "network": payload.get("network"),
                "system": system_info,
            })
        else:
            await ws_manager.broadcast_command_response(payload)

    async def _handle_reader_status(self, payload: dict[str, Any]) -> None:
        """Process reader status update.

        Args:
            payload: Status payload with reader info.
        """
        self._last_reader_status = payload
        status = payload.get("status", "unknown")
        uptime = payload.get("uptime", 0)

        logger.info(f"Reader status: {status}, uptime: {uptime}s")

        # Broadcast to WebSocket clients
        ws_manager = get_ws_manager()
        await ws_manager.broadcast_reader_status(payload)

    async def _handle_tag_detection(self, payload: dict[str, Any]) -> None:
        """Process tag detection from gate reader.

        Flow:
        1. Extract EPC (idHex) from payload
        2. Pass EPC to decision engine
        3. Decision engine decodes EPC → QR code
        4. Decision engine matches QR against database
        5. Broadcast result to WebSocket clients

        Args:
            payload: Message payload with tag data.
        """
        # Extract tag data - handle nested 'data' field
        data = payload.get("data", payload)
        # idHex is the raw EPC from the RFID reader
        epc = data.get("idHex") or data.get("tag_id")
        if not epc:
            logger.warning("Tag detection missing EPC (idHex)")
            return

        rssi = data.get("peakRssi") or data.get("rssi")
        antenna = data.get("antenna")
        gate_id = payload.get("clientId") or get_config().gate.client_id

        # Make decision (EPC is decoded to QR inside decision engine)
        engine = get_decision_engine()
        decision, reason, qr_code = await engine.make_decision(epc, gate_id, rssi, antenna)

        # Skip broadcasting for debounced or cooldown events
        if reason in ("debounced", "alarm_cooldown"):
            return

        # Broadcast to WebSocket clients (include both EPC and decoded QR)
        ws_manager = get_ws_manager()
        # Use QR code as the identifier for UI display (more meaningful than EPC)
        display_id = qr_code if qr_code else epc
        await ws_manager.broadcast_tag_detected(display_id, decision, rssi, antenna)

        if decision == Decision.ALARM:
            await ws_manager.broadcast_alarm_triggered(display_id, gate_id, rssi)
            # Trigger alarm on gate
            await self.trigger_alarm()

    async def trigger_alarm(self, duration: Optional[int] = None) -> None:
        """Trigger alarm GPO pulse on gate reader.

        Args:
            duration: Pulse duration in seconds. Uses config default if not specified.
        """
        if not self._client or not self._connected:
            logger.warning("Cannot trigger alarm: MQTT not connected")
            return

        config = get_config()
        topic = self._get_topic(config.gate.topic_gpo_cmd)
        pulse_duration = duration or config.gate.gpo_pulse_seconds

        payload_dict = {
            "action": "pulse",
            "gpo3": 1,
            "duration": pulse_duration,
        }
        payload = json.dumps(payload_dict)

        logger.debug(f"[PUB] Publishing alarm: topic={topic}, qos=1, payload={payload}")
        self._client.publish(topic, payload, qos=1)
        logger.info(f"[PUB] Alarm triggered: {pulse_duration}s pulse to {topic}")

    async def _auto_start_scan(self) -> None:
        """Auto-start inventory scan after MQTT connection.

        Called automatically when MQTT connects to start reading tags.
        """
        # Small delay to ensure connection is fully established
        await asyncio.sleep(1.0)
        logger.info("[AUTO] Starting inventory scan automatically...")
        await self.send_rfid_command("start")

    async def send_rfid_command(self, action: str) -> None:
        """Send RFID control command to gate reader.

        Args:
            action: Command action (start, stop, query, status).
        """
        if not self._client or not self._connected:
            logger.warning("Cannot send command: MQTT not connected")
            return

        config = get_config()
        topic = self._get_topic(config.gate.topic_rfid_cmd)

        payload = json.dumps({"action": action})
        logger.debug(f"[PUB] Publishing RFID command: topic={topic}, qos=1, payload={payload}")
        self._client.publish(topic, payload, qos=1)
        logger.info(f"[PUB] RFID command sent: action={action} to {topic}")

    async def set_antenna_power(
        self,
        antenna1: int = 20,
        antenna2: int = 20,
        antenna3: int = 15,
        antenna4: int = 15,
    ) -> None:
        """Set antenna power levels.

        Args:
            antenna1: Antenna 1 power (dBm).
            antenna2: Antenna 2 power (dBm).
            antenna3: Antenna 3 power (dBm).
            antenna4: Antenna 4 power (dBm).
        """
        if not self._client or not self._connected:
            logger.warning("Cannot set power: MQTT not connected")
            return

        config = get_config()
        topic = self._get_topic(config.gate.topic_power_cmd)

        payload_dict = {
            "action": "set",
            "ant1": antenna1,
            "ant2": antenna2,
            "ant3": antenna3,
            "ant4": antenna4,
        }
        payload = json.dumps(payload_dict)

        logger.debug(f"[PUB] Publishing antenna power: topic={topic}, qos=1, payload={payload}")
        self._client.publish(topic, payload, qos=1)
        logger.info(f"[PUB] Antenna power set: {antenna1}/{antenna2}/{antenna3}/{antenna4} to {topic}")

    async def get_antenna_power(self) -> None:
        """Query current antenna power levels from gate reader.

        The response will be received via data/response topic and stored
        in last_response property. It will also be broadcast via WebSocket.
        """
        if not self._client or not self._connected:
            logger.warning("Cannot get power: MQTT not connected")
            return

        config = get_config()
        topic = self._get_topic(config.gate.topic_power_cmd)

        payload = json.dumps({"action": "get"})
        logger.debug(f"[PUB] Publishing power query: topic={topic}, qos=1, payload={payload}")
        self._client.publish(topic, payload, qos=1)
        logger.info(f"[PUB] Antenna power query sent to {topic}")

    async def get_reader_status(self) -> None:
        """Query reader status (includes inventory status).

        The response will be received via data/response topic and stored
        in last_response property. It will also be broadcast via WebSocket.
        """
        if not self._client or not self._connected:
            logger.warning("Cannot get status: MQTT not connected")
            return

        config = get_config()
        topic = self._get_topic(config.gate.topic_rfid_cmd)

        payload = json.dumps({"action": "status"})
        logger.debug(f"[PUB] Publishing status query: topic={topic}, qos=1, payload={payload}")
        self._client.publish(topic, payload, qos=1)
        logger.info(f"[PUB] Reader status query sent to {topic}")

    def connect(self, loop: asyncio.AbstractEventLoop) -> None:
        """Connect to MQTT broker.

        Args:
            loop: Asyncio event loop for coroutine scheduling.
        """
        config = get_config()
        self._loop = loop

        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            protocol=mqtt.MQTTv5,
        )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.on_subscribe = self._on_subscribe

        if config.mqtt.username:
            self._client.username_pw_set(config.mqtt.username, config.mqtt.password)

        # Enable TLS if configured (required for HiveMQ Cloud and other secure brokers)
        if config.mqtt.use_tls:
            import certifi
            self._client.tls_set(ca_certs=certifi.where(), tls_version=ssl.PROTOCOL_TLS_CLIENT)
            logger.info("TLS enabled for MQTT connection")

        logger.info(f"Connecting to MQTT broker at {config.mqtt.host}:{config.mqtt.port}")

        try:
            self._client.connect_async(config.mqtt.host, config.mqtt.port)
            self._client.loop_start()
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")

    def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False
            logger.info("MQTT client disconnected")


# Global MQTT client instance
_mqtt_client: Optional[MqttClient] = None


def get_mqtt_client() -> MqttClient:
    """Get MQTT client instance (singleton)."""
    global _mqtt_client
    if _mqtt_client is None:
        _mqtt_client = MqttClient()
    return _mqtt_client

