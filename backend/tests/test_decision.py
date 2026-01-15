"""Tests for the decision engine service.

Tests the EPC → QR code decoding and matching logic.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from models import Decision, TagState
from mqtt_client import MqttClient
from services.decision import DecisionEngine
from services.epc_decoder import decode_epc


@pytest.fixture
def decision_engine() -> DecisionEngine:
    """Create a fresh decision engine for testing."""
    return DecisionEngine()


@pytest.fixture
def mock_config() -> dict:
    """Create mock configuration."""
    return {
        "decision": {
            "pass_when_in_cart": True,
            "debounce_ms": 100,
            "alarm_cooldown_ms": 500,
        }
    }


class TestEpcDecoder:
    """Test cases for EPC to QR code decoding."""

    def test_decode_letters(self) -> None:
        """Letters should be decoded from two-char pairs."""
        # A0→A, B0→B, C0→C
        assert decode_epc("A0B0C0") == "ABC"

    def test_decode_all_letters(self) -> None:
        """All letter mappings should work."""
        # Test A-F (row 0)
        assert decode_epc("A0B0C0D0E0F0") == "ABCDEF"
        # Test G-L (row 1)
        assert decode_epc("A1B1C1D1E1F1") == "GHIJKL"
        # Test M-R (row 2)
        assert decode_epc("A2B2C2D2E2F2") == "MNOPQR"
        # Test S-X (row 3)
        assert decode_epc("A3B3C3D3E3F3") == "STUVWX"
        # Test Y-Z (row 4)
        assert decode_epc("A4B4") == "YZ"

    def test_decode_numbers_passthrough(self) -> None:
        """Numbers should pass through unchanged."""
        assert decode_epc("123456789") == "123456789"

    def test_decode_mixed(self) -> None:
        """Mixed letters and numbers should decode correctly."""
        # A0→A, B0→B, C0→C, then 1234
        assert decode_epc("A0B0C01234") == "ABC1234"

    def test_decode_removes_trailing_f(self) -> None:
        """Trailing F's (padding) should be removed."""
        assert decode_epc("A0B0C01234FFFFFFFFFF") == "ABC1234"

    def test_decode_preserves_non_trailing_f(self) -> None:
        """Non-trailing F characters should be preserved."""
        # F0 decodes to 'F' letter
        assert decode_epc("F0F0") == "FF"

    def test_decode_empty_string(self) -> None:
        """Empty string should return empty."""
        assert decode_epc("") == ""

    def test_decode_case_insensitive(self) -> None:
        """Decoding should be case insensitive."""
        assert decode_epc("a0b0c0") == "ABC"


class TestDecisionEngine:
    """Test cases for DecisionEngine."""

    @pytest.mark.asyncio
    async def test_unknown_qr_triggers_alarm(
        self,
        decision_engine: DecisionEngine,
    ) -> None:
        """Unknown QR codes (decoded from EPC) should trigger alarm."""
        # EPC "A0B0C0" decodes to QR "ABC"
        test_epc = "A0B0C0FFFFFFFFFF"
        expected_qr = "ABC"

        with patch("services.decision.get_config") as mock_get_config, \
             patch("services.decision.get_qr_state", new_callable=AsyncMock) as mock_get_qr, \
             patch("services.decision.insert_alarm_event", new_callable=AsyncMock) as mock_alarm:

            mock_get_config.return_value.decision.debounce_ms = 0
            mock_get_config.return_value.decision.alarm_cooldown_ms = 0
            mock_get_qr.return_value = None

            decision, reason, qr_code = await decision_engine.make_decision(
                epc=test_epc,
                gate_id="gate_01",
            )

            assert decision == Decision.ALARM
            assert reason == "qr_not_found"
            assert qr_code == expected_qr
            # Verify alarm was recorded with both EPC and QR
            mock_alarm.assert_called_once()
            call_args = mock_alarm.call_args
            assert call_args[0][1] == test_epc  # epc
            assert call_args[0][2] == expected_qr  # qr_code

    @pytest.mark.asyncio
    async def test_paid_qr_passes(
        self,
        decision_engine: DecisionEngine,
    ) -> None:
        """Paid QR codes should always pass."""
        test_epc = "B3E0A3B3FFFF"  # Decodes to "TEST"

        with patch("services.decision.get_config") as mock_get_config, \
             patch("services.decision.get_qr_state", new_callable=AsyncMock) as mock_get_qr:

            mock_get_config.return_value.decision.debounce_ms = 0
            mock_get_qr.return_value = {
                "state": TagState.PAID.value,
                "qr_code": "TEST",
            }

            decision, reason, qr_code = await decision_engine.make_decision(
                epc=test_epc,
                gate_id="gate_01",
            )

            assert decision == Decision.PASS
            assert reason == "paid"

    @pytest.mark.asyncio
    async def test_in_cart_qr_passes_when_allowed(
        self,
        decision_engine: DecisionEngine,
    ) -> None:
        """In-cart QR codes should pass when pass_when_in_cart is enabled."""
        test_epc = "A0B0C0FFFF"  # Decodes to "ABC"

        with patch("services.decision.get_config") as mock_get_config, \
             patch("services.decision.get_qr_state", new_callable=AsyncMock) as mock_get_qr:

            mock_get_config.return_value.decision.debounce_ms = 0
            mock_get_config.return_value.decision.pass_when_in_cart = True
            mock_get_qr.return_value = {
                "state": TagState.IN_CART.value,
                "qr_code": "ABC",
            }

            decision, reason, qr_code = await decision_engine.make_decision(
                epc=test_epc,
                gate_id="gate_01",
            )

            assert decision == Decision.PASS
            assert reason == "in_cart_allowed"

    @pytest.mark.asyncio
    async def test_in_cart_qr_alarms_when_not_allowed(
        self,
        decision_engine: DecisionEngine,
    ) -> None:
        """In-cart QR codes should alarm when pass_when_in_cart is disabled."""
        test_epc = "A0B0C0FFFF"

        with patch("services.decision.get_config") as mock_get_config, \
             patch("services.decision.get_qr_state", new_callable=AsyncMock) as mock_get_qr, \
             patch("services.decision.insert_alarm_event", new_callable=AsyncMock):

            mock_get_config.return_value.decision.debounce_ms = 0
            mock_get_config.return_value.decision.alarm_cooldown_ms = 0
            mock_get_config.return_value.decision.pass_when_in_cart = False
            mock_get_qr.return_value = {
                "state": TagState.IN_CART.value,
                "qr_code": "ABC",
            }

            decision, reason, qr_code = await decision_engine.make_decision(
                epc=test_epc,
                gate_id="gate_01",
            )

            assert decision == Decision.ALARM
            assert reason == "in_cart_not_allowed"

    def test_cleanup_old_entries(
        self,
        decision_engine: DecisionEngine,
    ) -> None:
        """Should clean up old tracking entries."""
        # Add some entries (keyed by EPC now)
        decision_engine._last_seen["A0B0C0FFFF"] = 0
        decision_engine._last_alarm["A0B0C0FFFF"] = 0

        removed = decision_engine.cleanup_old_entries(max_age_seconds=1)

        assert removed == 2
        assert "A0B0C0FFFF" not in decision_engine._last_seen
        assert "A0B0C0FFFF" not in decision_engine._last_alarm


class TestMqttTagDetection:
    """Test cases for MQTT tag detection payload handling."""

    @pytest.fixture
    def mqtt_client(self) -> MqttClient:
        """Create a fresh MQTT client for testing."""
        return MqttClient()

    @pytest.mark.asyncio
    async def test_nextwaves_format_single_tag(self, mqtt_client: MqttClient) -> None:
        """Nextwaves format with single tag in array should be processed."""
        payload = {
            "tags": [{"epc": "30396062C38DA1C0007D4881", "rssi": -48, "ant": 3, "n": 52}],
            "ts": "1970-01-01T10:02:12.520+0700",
            "id": "nextwaves-2de8",
            "cnt": 1,
        }

        with patch.object(mqtt_client, "_process_single_tag", new_callable=AsyncMock) as mock_process:
            await mqtt_client._handle_tag_detection(payload)

            mock_process.assert_called_once_with(
                "30396062C38DA1C0007D4881",
                "nextwaves-2de8",
                -48,
                3,
            )

    @pytest.mark.asyncio
    async def test_nextwaves_format_multiple_tags(self, mqtt_client: MqttClient) -> None:
        """Nextwaves format with multiple tags should process all."""
        payload = {
            "tags": [
                {"epc": "EPC001", "rssi": -45, "ant": 1},
                {"epc": "EPC002", "rssi": -50, "ant": 2},
                {"epc": "EPC003", "rssi": -55, "ant": 3},
            ],
            "id": "reader-01",
            "cnt": 3,
        }

        with patch.object(mqtt_client, "_process_single_tag", new_callable=AsyncMock) as mock_process:
            await mqtt_client._handle_tag_detection(payload)

            assert mock_process.call_count == 3
            mock_process.assert_any_call("EPC001", "reader-01", -45, 1)
            mock_process.assert_any_call("EPC002", "reader-01", -50, 2)
            mock_process.assert_any_call("EPC003", "reader-01", -55, 3)

    @pytest.mark.asyncio
    async def test_legacy_format_with_data_field(self, mqtt_client: MqttClient) -> None:
        """Legacy format with nested data field should be processed."""
        payload = {
            "data": {"idHex": "LEGACY_EPC_001", "peakRssi": -40, "antenna": 2},
            "clientId": "legacy-gate-01",
        }

        with patch.object(mqtt_client, "_process_single_tag", new_callable=AsyncMock) as mock_process:
            await mqtt_client._handle_tag_detection(payload)

            mock_process.assert_called_once_with(
                "LEGACY_EPC_001",
                "legacy-gate-01",
                -40,
                2,
            )

    @pytest.mark.asyncio
    async def test_legacy_format_flat_structure(self, mqtt_client: MqttClient) -> None:
        """Legacy format with flat structure should be processed."""
        payload = {
            "idHex": "FLAT_EPC_001",
            "peakRssi": -35,
            "antenna": 1,
            "clientId": "flat-gate-01",
        }

        with patch.object(mqtt_client, "_process_single_tag", new_callable=AsyncMock) as mock_process:
            await mqtt_client._handle_tag_detection(payload)

            mock_process.assert_called_once_with(
                "FLAT_EPC_001",
                "flat-gate-01",
                -35,
                1,
            )

    @pytest.mark.asyncio
    async def test_nextwaves_format_with_epc_field_alias(self, mqtt_client: MqttClient) -> None:
        """Nextwaves format should also accept idHex in tag array."""
        payload = {
            "tags": [{"idHex": "ALIAS_EPC", "rssi": -42, "ant": 4}],
            "id": "reader-02",
        }

        with patch.object(mqtt_client, "_process_single_tag", new_callable=AsyncMock) as mock_process:
            await mqtt_client._handle_tag_detection(payload)

            mock_process.assert_called_once_with("ALIAS_EPC", "reader-02", -42, 4)

    @pytest.mark.asyncio
    async def test_legacy_format_with_epc_field(self, mqtt_client: MqttClient) -> None:
        """Legacy format should also accept epc field."""
        payload = {
            "epc": "LEGACY_EPC_FIELD",
            "rssi": -38,
            "ant": 2,
            "clientId": "gate-03",
        }

        with patch.object(mqtt_client, "_process_single_tag", new_callable=AsyncMock) as mock_process:
            await mqtt_client._handle_tag_detection(payload)

            mock_process.assert_called_once_with("LEGACY_EPC_FIELD", "gate-03", -38, 2)

    @pytest.mark.asyncio
    async def test_missing_epc_in_tags_array_skipped(self, mqtt_client: MqttClient) -> None:
        """Tags without EPC in array should be skipped with warning."""
        payload = {
            "tags": [
                {"rssi": -45, "ant": 1},  # Missing EPC - should be skipped
                {"epc": "VALID_EPC", "rssi": -50, "ant": 2},
            ],
            "id": "reader-01",
        }

        with patch.object(mqtt_client, "_process_single_tag", new_callable=AsyncMock) as mock_process:
            await mqtt_client._handle_tag_detection(payload)

            # Only the valid tag should be processed
            mock_process.assert_called_once_with("VALID_EPC", "reader-01", -50, 2)

    @pytest.mark.asyncio
    async def test_missing_epc_in_legacy_format_returns_early(self, mqtt_client: MqttClient) -> None:
        """Legacy format without EPC should return early."""
        payload = {
            "data": {"peakRssi": -40, "antenna": 2},
            "clientId": "gate-01",
        }

        with patch.object(mqtt_client, "_process_single_tag", new_callable=AsyncMock) as mock_process:
            await mqtt_client._handle_tag_detection(payload)

            mock_process.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_to_config_gate_id(self, mqtt_client: MqttClient) -> None:
        """Should fallback to config gate_id when not in payload."""
        payload = {
            "tags": [{"epc": "TEST_EPC", "rssi": -45, "ant": 1}],
            # No 'id' or 'clientId' field
        }

        with patch.object(mqtt_client, "_process_single_tag", new_callable=AsyncMock) as mock_process, \
             patch("mqtt_client.get_config") as mock_config:
            mock_config.return_value.gate.client_id = "default-gate"

            await mqtt_client._handle_tag_detection(payload)

            mock_process.assert_called_once_with("TEST_EPC", "default-gate", -45, 1)

