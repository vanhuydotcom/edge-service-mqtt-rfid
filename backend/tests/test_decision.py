"""Tests for the decision engine service.

Tests the EPC → QR code decoding and matching logic.
"""

import pytest
from unittest.mock import AsyncMock, patch

from models import Decision, TagState
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

