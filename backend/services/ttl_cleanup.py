"""TTL Cleanup Service for RFID Edge Service.

Background task that periodically removes expired tags from the database.
"""

import asyncio
import logging
from typing import Optional

from config import get_config
from database import cleanup_expired_tags
from services.decision import get_decision_engine

logger = logging.getLogger(__name__)

# Task reference for cleanup
_cleanup_task: Optional[asyncio.Task[None]] = None


async def _run_cleanup_loop() -> None:
    """Run the TTL cleanup loop.

    Continuously cleans up expired tags at configured intervals.
    Also cleans up old decision engine entries.
    Config is re-read on each iteration to support hot-reload.
    """
    logger.info("TTL cleanup service started")

    while True:
        try:
            # Re-read config on each iteration to support hot-reload
            config = get_config()
            interval = config.ttl.cleanup_interval_seconds

            # Clean up expired tags
            deleted = await cleanup_expired_tags()
            if deleted > 0:
                logger.info(f"TTL cleanup: removed {deleted} expired tags")

            # Clean up decision engine tracking
            engine = get_decision_engine()
            engine.cleanup_old_entries(max_age_seconds=3600)

            # Sleep before next cleanup cycle
            await asyncio.sleep(interval)

        except asyncio.CancelledError:
            logger.info("TTL cleanup service stopping")
            break
        except Exception as e:
            logger.error(f"Error in TTL cleanup: {e}", exc_info=True)
            # Continue running despite errors
            await asyncio.sleep(10)


def start_cleanup_service() -> asyncio.Task[None]:
    """Start the TTL cleanup background service.

    Returns:
        Asyncio task running the cleanup loop.
    """
    global _cleanup_task

    if _cleanup_task is not None and not _cleanup_task.done():
        logger.warning("Cleanup service already running")
        return _cleanup_task

    _cleanup_task = asyncio.create_task(_run_cleanup_loop())
    return _cleanup_task


async def stop_cleanup_service() -> None:
    """Stop the TTL cleanup background service."""
    global _cleanup_task

    if _cleanup_task is not None and not _cleanup_task.done():
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass
        logger.info("TTL cleanup service stopped")

    _cleanup_task = None

