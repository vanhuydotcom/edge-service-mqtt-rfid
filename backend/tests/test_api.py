"""Tests for REST API endpoints.

Tests the QR code registration and lookup API.
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client with mocked dependencies."""
    with patch("main.init_db", new_callable=AsyncMock), \
         patch("main.close_db", new_callable=AsyncMock), \
         patch("main.get_mqtt_client") as mock_mqtt, \
         patch("main.start_cleanup_service"), \
         patch("main.stop_cleanup_service", new_callable=AsyncMock), \
         patch("main.get_ws_manager") as mock_ws:

        mock_mqtt.return_value.is_connected = True
        mock_mqtt.return_value.last_tag_seen_seconds = 5
        mock_mqtt.return_value.connect = lambda x: None
        mock_mqtt.return_value.disconnect = lambda: None
        mock_ws.return_value.start_status_updates = lambda x: None
        mock_ws.return_value.stop_status_updates = AsyncMock()

        from main import app
        with TestClient(app) as c:
            yield c


class TestHealthEndpoint:
    """Test cases for health check endpoint."""

    def test_health_returns_ok(self, client: TestClient) -> None:
        """Health endpoint should return OK status."""
        with patch("main.get_tag_counts", new_callable=AsyncMock) as mock_counts:
            mock_counts.return_value = {"in_cart_count": 0, "paid_count": 0}

            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert "mqtt_connected" in data
            assert "db_ok" in data


class TestTagsEndpoints:
    """Test cases for tags API endpoints (QR code based)."""

    def test_register_qr_codes_in_cart(self, client: TestClient) -> None:
        """Should register QR codes with IN_CART state."""
        with patch("routers.tags.upsert_qr_codes_in_cart", new_callable=AsyncMock) as mock_upsert:
            mock_upsert.return_value = (3, 0)

            response = client.post(
                "/v1/tags/in-cart",
                json={
                    "store_id": "TEST",
                    "pos_id": "POS-01",
                    "order_id": "ORDER-001",
                    "ttl_seconds": 3600,
                    "qr_codes": ["QR001", "QR002", "QR003"],
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert data["upserted"] == 3
            assert data["ignored_paid"] == 0

    def test_register_qr_codes_paid(self, client: TestClient) -> None:
        """Should register QR codes with PAID state."""
        with patch("routers.tags.upsert_qr_codes_paid", new_callable=AsyncMock) as mock_upsert:
            mock_upsert.return_value = 2

            response = client.post(
                "/v1/tags/paid",
                json={
                    "store_id": "TEST",
                    "pos_id": "POS-01",
                    "order_id": "ORDER-001",
                    "ttl_seconds": 86400,
                    "qr_codes": ["QR001", "QR002"],
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert data["upserted"] == 2

    def test_remove_qr_codes(self, client: TestClient) -> None:
        """Should remove QR codes from database."""
        with patch("routers.tags.remove_qr_codes", new_callable=AsyncMock) as mock_remove:
            mock_remove.return_value = 1

            response = client.post(
                "/v1/tags/remove",
                json={
                    "order_id": "ORDER-001",
                    "qr_codes": ["QR001"],
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert data["deleted"] == 1

    def test_lookup_by_qr_code_not_found(self, client: TestClient) -> None:
        """Should return not found for unknown QR code."""
        with patch("routers.tags.get_qr_state", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            response = client.get("/v1/tags/lookup?qr_code=UNKNOWN_QR")

            assert response.status_code == 200
            data = response.json()
            assert data["qr_code"] == "UNKNOWN_QR"
            assert data["present"] is False

    def test_lookup_by_epc_decodes_correctly(self, client: TestClient) -> None:
        """Should decode EPC to QR code and lookup."""
        # EPC "A0B0C0FFFF" decodes to "ABC"
        with patch("routers.tags.get_qr_state", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            response = client.get("/v1/tags/lookup?epc=A0B0C0FFFF")

            assert response.status_code == 200
            data = response.json()
            assert data["qr_code"] == "ABC"  # Decoded from EPC
            assert data["epc"] == "A0B0C0FFFF"  # Original EPC preserved
            assert data["present"] is False

    def test_validation_error_empty_qr_codes(self, client: TestClient) -> None:
        """Should return validation error for empty qr_codes list."""
        response = client.post(
            "/v1/tags/in-cart",
            json={
                "store_id": "TEST",
                "pos_id": "POS-01",
                "order_id": "ORDER-001",
                "qr_codes": [],
            },
        )

        assert response.status_code == 422  # Validation error

    def test_lookup_requires_qr_or_epc(self, client: TestClient) -> None:
        """Should return error when neither qr_code nor epc is provided."""
        response = client.get("/v1/tags/lookup")

        assert response.status_code == 400
        data = response.json()
        assert "qr_code or epc" in data["detail"].lower()

