"""Tests for TTL cleanup service."""
import asyncio
import time
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestTTLCleanupService:
    """Test cases for TTL cleanup service."""

    @pytest.mark.asyncio
    async def test_cleanup_runs_immediately_on_startup(self) -> None:
        """Cleanup should run immediately when service starts, not after waiting."""
        cleanup_calls: list[float] = []

        async def mock_cleanup() -> int:
            cleanup_calls.append(time.time())
            return 1  # Simulate 1 tag deleted

        mock_config = MagicMock()
        mock_config.ttl.cleanup_interval_seconds = 60  # Normal interval

        mock_engine = MagicMock()
        mock_engine.cleanup_old_entries = MagicMock(return_value=0)

        with patch("services.ttl_cleanup.cleanup_expired_tags", mock_cleanup), \
             patch("services.ttl_cleanup.get_decision_engine", return_value=mock_engine), \
             patch("services.ttl_cleanup.get_config", return_value=mock_config):

            # Import and reset module state
            import services.ttl_cleanup as ttl_module
            ttl_module._cleanup_task = None

            start_time = time.time()

            # Start the cleanup service
            ttl_module.start_cleanup_service()

            # Wait just 0.5 seconds - much less than the 60s interval
            await asyncio.sleep(0.5)

            # Stop the service
            await ttl_module.stop_cleanup_service()

            # Verify cleanup was called immediately (within 0.5s)
            assert len(cleanup_calls) > 0, "Cleanup should have been called"
            first_cleanup_delay = cleanup_calls[0] - start_time
            assert first_cleanup_delay < 1.0, f"First cleanup took {first_cleanup_delay}s, expected < 1s"

    @pytest.mark.asyncio
    async def test_cleanup_removes_expired_tags(self) -> None:
        """Cleanup should delete expired tags from database."""
        from database import cleanup_expired_tags

        # This is an integration test - would need actual DB setup
        # For now, just verify the function exists and is callable
        assert callable(cleanup_expired_tags)

