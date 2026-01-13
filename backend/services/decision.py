"""Decision Engine for RFID Security Gate.

Implements PASS/ALARM logic based on tag state and configuration.

Data Flow:
1. Security gate reads EPC from RFID tag
2. DecisionEngine receives EPC via MQTT
3. EPC is decoded to QR code using decode_epc()
4. QR code is matched against stored QR codes in database
5. Decision (PASS/ALARM) is made based on state
"""

import logging
import time
from typing import Optional

from config import get_config
from database import get_qr_state, insert_alarm_event
from models import Decision, TagState
from services.epc_decoder import decode_epc

logger = logging.getLogger(__name__)


class DecisionEngine:
    """Handles gate pass/alarm decisions for detected tags.

    Implements debouncing and cooldown to prevent duplicate events.
    """

    def __init__(self) -> None:
        """Initialize decision engine with empty tracking dictionaries."""
        # Track last seen time for each EPC (debouncing)
        self._last_seen: dict[str, float] = {}
        # Track last alarm time for each EPC (cooldown)
        self._last_alarm: dict[str, float] = {}

    def _should_debounce(self, epc: str) -> bool:
        """Check if EPC event should be debounced.

        Args:
            epc: RFID EPC identifier.

        Returns:
            True if event should be ignored (within debounce window).
        """
        config = get_config()
        debounce_ms = config.decision.debounce_ms
        now = time.time() * 1000  # Convert to milliseconds

        last_time = self._last_seen.get(epc, 0)
        if now - last_time < debounce_ms:
            return True

        self._last_seen[epc] = now
        return False

    def _is_in_alarm_cooldown(self, epc: str) -> bool:
        """Check if EPC is in alarm cooldown period.

        Args:
            epc: RFID EPC identifier.

        Returns:
            True if alarm should be suppressed (within cooldown window).
        """
        config = get_config()
        cooldown_ms = config.decision.alarm_cooldown_ms
        now = time.time() * 1000

        last_alarm = self._last_alarm.get(epc, 0)
        return now - last_alarm < cooldown_ms

    def _record_alarm(self, epc: str) -> None:
        """Record alarm timestamp for cooldown tracking.

        Args:
            epc: RFID EPC identifier.
        """
        self._last_alarm[epc] = time.time() * 1000

    async def make_decision(
        self,
        epc: str,
        gate_id: str,
        rssi: Optional[float] = None,
        antenna: Optional[int] = None,
    ) -> tuple[Decision, str, str]:
        """Make PASS/ALARM decision for a detected tag.

        Flow:
        1. Debounce check (by EPC)
        2. Decode EPC → QR code
        3. Look up QR code in database
        4. Return decision based on state

        Args:
            epc: RFID EPC identifier (raw from gate reader).
            gate_id: Gate reader identifier.
            rssi: Signal strength (dBm).
            antenna: Antenna number that detected the tag.

        Returns:
            Tuple of (Decision, reasoning string, decoded QR code).
        """
        config = get_config()

        # Check debounce first (by EPC to avoid decoding on every read)
        if self._should_debounce(epc):
            logger.debug(f"EPC {epc} debounced")
            return Decision.PASS, "debounced", ""

        # Decode EPC to QR code
        
        qr_code = decode_epc(epc)
        logger.debug(f"Decoded EPC {epc} → QR {qr_code}")

        # Get QR code state from database
        qr_data = await get_qr_state(qr_code)

        if qr_data is None:
            # QR code not found - ALARM
            if self._is_in_alarm_cooldown(epc):
                logger.debug(f"EPC {epc} (QR: {qr_code}) in alarm cooldown")
                return Decision.PASS, "alarm_cooldown", qr_code

            self._record_alarm(epc)
            await insert_alarm_event(gate_id, epc, qr_code, rssi, antenna)
            logger.warning(f"ALARM: Unknown QR {qr_code} (EPC: {epc}) at gate {gate_id}")
            return Decision.ALARM, "qr_not_found", qr_code

        state = TagState(qr_data["state"])

        if state == TagState.PAID:
            # Paid QR - PASS
            logger.info(f"PASS: Paid QR {qr_code} (EPC: {epc}) at gate {gate_id}")
            return Decision.PASS, "paid", qr_code

        if state == TagState.IN_CART:
            if config.decision.pass_when_in_cart:
                # Configured to pass in-cart tags
                logger.info(f"PASS: In-cart QR {qr_code} (EPC: {epc}) at gate {gate_id} (pass_when_in_cart=true)")
                return Decision.PASS, "in_cart_allowed", qr_code
            else:
                # In-cart but not paid - ALARM
                if self._is_in_alarm_cooldown(epc):
                    logger.debug(f"EPC {epc} (QR: {qr_code}) in alarm cooldown")
                    return Decision.PASS, "alarm_cooldown", qr_code

                self._record_alarm(epc)
                await insert_alarm_event(gate_id, epc, qr_code, rssi, antenna)
                logger.warning(f"ALARM: In-cart (not paid) QR {qr_code} (EPC: {epc}) at gate {gate_id}")
                return Decision.ALARM, "in_cart_not_allowed", qr_code

        # Fallback - should not reach here
        logger.error(f"Unknown state {state} for QR {qr_code}")
        return Decision.ALARM, "unknown_state", qr_code

    def cleanup_old_entries(self, max_age_seconds: int = 3600) -> int:
        """Clean up old entries from tracking dictionaries.

        Args:
            max_age_seconds: Maximum age of entries to keep.

        Returns:
            Number of entries removed.
        """
        now = time.time() * 1000
        max_age_ms = max_age_seconds * 1000
        removed = 0

        # Clean last_seen
        old_tags = [k for k, v in self._last_seen.items() if now - v > max_age_ms]
        for tag in old_tags:
            del self._last_seen[tag]
            removed += 1

        # Clean last_alarm
        old_alarms = [k for k, v in self._last_alarm.items() if now - v > max_age_ms]
        for tag in old_alarms:
            del self._last_alarm[tag]
            removed += 1

        if removed > 0:
            logger.debug(f"Cleaned up {removed} old decision engine entries")
        return removed


# Global decision engine instance
_decision_engine: Optional[DecisionEngine] = None


def get_decision_engine() -> DecisionEngine:
    """Get decision engine instance (singleton)."""
    global _decision_engine
    if _decision_engine is None:
        _decision_engine = DecisionEngine()
    return _decision_engine

