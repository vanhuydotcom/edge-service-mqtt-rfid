"""SQLite database management for RFID Edge Service.

Provides async database operations using aiosqlite.

Data Flow:
- POS sends QR codes → stored in `qr_code` column
- Security gate scans EPC → decode_epc() → match against stored qr_code
- Database stores QR codes as the canonical identifier
"""

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

import aiosqlite

from config import get_config
from models import AlarmEvent, TagState

logger = logging.getLogger(__name__)

# Database connection pool
_db: Optional[aiosqlite.Connection] = None


# --- Schema Definitions ---

# NOTE: qr_code is the canonical identifier (what POS sends)
# Security gate EPCs are decoded to QR codes for matching
SCHEMA_TAG_STATE = """
CREATE TABLE IF NOT EXISTS tag_state (
    qr_code       TEXT PRIMARY KEY,
    state         TEXT NOT NULL,
    order_id      TEXT,
    pos_id        TEXT,
    store_id      TEXT,
    updated_at    INTEGER NOT NULL,
    expires_at    INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tag_state_expires_at ON tag_state(expires_at);
CREATE INDEX IF NOT EXISTS idx_tag_state_state ON tag_state(state);
CREATE INDEX IF NOT EXISTS idx_tag_state_order_id ON tag_state(order_id);
"""

# NOTE: alarm_event stores both EPC (from gate) and decoded QR code for reference
SCHEMA_ALARM_EVENT = """
CREATE TABLE IF NOT EXISTS alarm_event (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    gate_id       TEXT NOT NULL,
    epc           TEXT NOT NULL,
    qr_code       TEXT,
    rssi          REAL,
    antenna       INTEGER,
    created_at    INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alarm_event_created_at ON alarm_event(created_at);
CREATE INDEX IF NOT EXISTS idx_alarm_event_qr_code ON alarm_event(qr_code);
"""


async def _migrate_schema(db: aiosqlite.Connection) -> None:
    """Migrate database schema from old version to new.

    Handles migration from tag_id-based schema to qr_code-based schema.
    """
    # Check if we have old tag_state table with tag_id column
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tag_state'"
    )
    table_exists = await cursor.fetchone()

    if table_exists:
        # Check if it has old schema (tag_id instead of qr_code)
        cursor = await db.execute("PRAGMA table_info(tag_state)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        if 'tag_id' in column_names and 'qr_code' not in column_names:
            logger.info("Migrating tag_state table from tag_id to qr_code schema...")
            # Rename old table
            await db.execute("ALTER TABLE tag_state RENAME TO tag_state_old")
            # Create new table with correct schema
            await db.executescript(SCHEMA_TAG_STATE)
            # Copy data (tag_id becomes qr_code)
            await db.execute("""
                INSERT INTO tag_state (qr_code, state, order_id, pos_id, store_id, updated_at, expires_at)
                SELECT tag_id, state, order_id, pos_id, store_id, updated_at, expires_at
                FROM tag_state_old
            """)
            # Drop old table
            await db.execute("DROP TABLE tag_state_old")
            await db.commit()
            logger.info("Migration complete: tag_state")

    # Check if alarm_event needs migration (add qr_code column)
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='alarm_event'"
    )
    alarm_table_exists = await cursor.fetchone()

    if alarm_table_exists:
        cursor = await db.execute("PRAGMA table_info(alarm_event)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        if 'qr_code' not in column_names:
            logger.info("Migrating alarm_event table to add qr_code column...")
            # Add qr_code column if it doesn't exist
            await db.execute("ALTER TABLE alarm_event ADD COLUMN qr_code TEXT")
            await db.commit()
            logger.info("Migration complete: alarm_event")

        # Check if epc column exists (old schema had tag_id)
        if 'tag_id' in column_names and 'epc' not in column_names:
            logger.info("Migrating alarm_event table from tag_id to epc...")
            await db.execute("ALTER TABLE alarm_event RENAME TO alarm_event_old")
            await db.executescript(SCHEMA_ALARM_EVENT)
            await db.execute("""
                INSERT INTO alarm_event (id, gate_id, epc, qr_code, rssi, antenna, created_at)
                SELECT id, gate_id, tag_id, NULL, rssi, antenna, created_at
                FROM alarm_event_old
            """)
            await db.execute("DROP TABLE alarm_event_old")
            await db.commit()
            logger.info("Migration complete: alarm_event tag_id -> epc")


async def init_db() -> aiosqlite.Connection:
    """Initialize database connection and create tables.

    Returns:
        Database connection instance.
    """
    global _db

    config = get_config()
    db_path = Path(config.storage.sqlite_path)

    # Ensure directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Initializing database at: {db_path}")

    _db = await aiosqlite.connect(str(db_path))
    _db.row_factory = aiosqlite.Row

    # Enable foreign keys
    await _db.execute("PRAGMA foreign_keys = ON")

    # Run migrations for existing databases
    await _migrate_schema(_db)

    # Create tables (if not exist)
    await _db.executescript(SCHEMA_TAG_STATE)
    await _db.executescript(SCHEMA_ALARM_EVENT)
    await _db.commit()

    logger.info("Database initialized successfully")
    return _db


async def get_db() -> aiosqlite.Connection:
    """Get database connection (dependency injection).

    Returns:
        Active database connection.

    Raises:
        RuntimeError: If database not initialized.
    """
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db


async def close_db() -> None:
    """Close database connection."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None
        logger.info("Database connection closed")


# --- Tag State Operations ---


async def get_qr_state(qr_code: str) -> Optional[dict[str, Any]]:
    """Retrieve QR code state from database.

    Args:
        qr_code: QR code identifier (canonical identifier from POS).

    Returns:
        Tag state dict if found and not expired, None otherwise.
    """
    db = await get_db()
    now = int(time.time())

    async with db.execute(
        "SELECT * FROM tag_state WHERE qr_code = ? AND expires_at >= ?",
        (qr_code, now),
    ) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None


# Alias for backward compatibility
get_tag_state = get_qr_state


async def upsert_qr_codes_in_cart(
    qr_codes: list[str],
    order_id: str,
    pos_id: str,
    store_id: str,
    ttl_seconds: int,
) -> tuple[int, int]:
    """Insert or update QR codes with IN_CART state.

    Does NOT overwrite QR codes that are already PAID.

    Args:
        qr_codes: List of QR codes from POS.
        order_id: Order identifier.
        pos_id: POS terminal identifier.
        store_id: Store identifier.
        ttl_seconds: Time-to-live in seconds.

    Returns:
        Tuple of (upserted_count, ignored_paid_count).
    """
    db = await get_db()
    now = int(time.time())
    expires_at = now + ttl_seconds

    upserted = 0
    ignored_paid = 0

    for qr_code in qr_codes:
        # Check if QR code is already PAID
        existing = await get_qr_state(qr_code)
        if existing and existing["state"] == TagState.PAID.value:
            ignored_paid += 1
            continue

        # Upsert with IN_CART state
        await db.execute(
            """
            INSERT INTO tag_state (qr_code, state, order_id, pos_id, store_id, updated_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(qr_code) DO UPDATE SET
                state = excluded.state,
                order_id = excluded.order_id,
                pos_id = excluded.pos_id,
                store_id = excluded.store_id,
                updated_at = excluded.updated_at,
                expires_at = excluded.expires_at
            WHERE state != 'PAID'
            """,
            (qr_code, TagState.IN_CART.value, order_id, pos_id, store_id, now, expires_at),
        )
        upserted += 1

    await db.commit()
    return upserted, ignored_paid


# Alias for backward compatibility
upsert_tags_in_cart = upsert_qr_codes_in_cart


async def upsert_qr_codes_paid(
    qr_codes: list[str],
    order_id: str,
    pos_id: str,
    store_id: str,
    ttl_seconds: int,
) -> int:
    """Insert or update QR codes with PAID state.

    PAID state always overwrites IN_CART.

    Args:
        qr_codes: List of QR codes from POS.
        order_id: Order identifier.
        pos_id: POS terminal identifier.
        store_id: Store identifier.
        ttl_seconds: Time-to-live in seconds.

    Returns:
        Number of QR codes upserted.
    """
    db = await get_db()
    now = int(time.time())
    expires_at = now + ttl_seconds

    for qr_code in qr_codes:
        await db.execute(
            """
            INSERT INTO tag_state (qr_code, state, order_id, pos_id, store_id, updated_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(qr_code) DO UPDATE SET
                state = excluded.state,
                order_id = excluded.order_id,
                pos_id = excluded.pos_id,
                store_id = excluded.store_id,
                updated_at = excluded.updated_at,
                expires_at = excluded.expires_at
            """,
            (qr_code, TagState.PAID.value, order_id, pos_id, store_id, now, expires_at),
        )

    await db.commit()
    return len(qr_codes)


# Alias for backward compatibility
upsert_tags_paid = upsert_qr_codes_paid


async def remove_qr_codes(qr_codes: list[str], order_id: Optional[str] = None) -> int:
    """Remove QR codes from database.

    Args:
        qr_codes: List of QR codes to remove.
        order_id: Optional order ID filter.

    Returns:
        Number of QR codes deleted.
    """
    db = await get_db()

    if order_id:
        placeholders = ",".join("?" * len(qr_codes))
        await db.execute(
            f"DELETE FROM tag_state WHERE qr_code IN ({placeholders}) AND order_id = ?",
            (*qr_codes, order_id),
        )
    else:
        placeholders = ",".join("?" * len(qr_codes))
        await db.execute(
            f"DELETE FROM tag_state WHERE qr_code IN ({placeholders})",
            qr_codes,
        )

    await db.commit()
    return db.total_changes


# Alias for backward compatibility
remove_tags = remove_qr_codes


async def cleanup_expired_tags() -> int:
    """Remove expired tags from database.

    Returns:
        Number of tags deleted.
    """
    db = await get_db()
    now = int(time.time())

    await db.execute("DELETE FROM tag_state WHERE expires_at < ?", (now,))
    await db.commit()

    deleted = db.total_changes
    if deleted > 0:
        logger.info(f"Cleaned up {deleted} expired tags")
    return deleted


async def get_tag_counts() -> dict[str, int]:
    """Get counts of tags by state.

    Returns:
        Dict with 'in_cart_count' and 'paid_count'.
    """
    db = await get_db()
    now = int(time.time())

    async with db.execute(
        """
        SELECT state, COUNT(*) as count
        FROM tag_state
        WHERE expires_at >= ?
        GROUP BY state
        """,
        (now,),
    ) as cursor:
        rows = await cursor.fetchall()

    counts = {"in_cart_count": 0, "paid_count": 0}
    for row in rows:
        if row["state"] == TagState.IN_CART.value:
            counts["in_cart_count"] = row["count"]
        elif row["state"] == TagState.PAID.value:
            counts["paid_count"] = row["count"]

    return counts


# --- Alarm Event Operations ---


async def insert_alarm_event(
    gate_id: str,
    epc: str,
    qr_code: Optional[str] = None,
    rssi: Optional[float] = None,
    antenna: Optional[int] = None,
) -> int:
    """Insert alarm event record.

    Args:
        gate_id: Gate identifier.
        epc: Raw EPC from RFID gate reader.
        qr_code: Decoded QR code (from decode_epc).
        rssi: Signal strength.
        antenna: Antenna number.

    Returns:
        ID of inserted record.
    """
    db = await get_db()
    now = int(time.time())

    cursor = await db.execute(
        "INSERT INTO alarm_event (gate_id, epc, qr_code, rssi, antenna, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (gate_id, epc, qr_code, rssi, antenna, now),
    )
    await db.commit()
    return cursor.lastrowid or 0


async def get_alarms_count_24h() -> int:
    """Get count of alarms in last 24 hours.

    Returns:
        Number of alarms.
    """
    db = await get_db()
    now = int(time.time())
    day_ago = now - 86400

    async with db.execute(
        "SELECT COUNT(*) as count FROM alarm_event WHERE created_at >= ?",
        (day_ago,),
    ) as cursor:
        row = await cursor.fetchone()
        return row["count"] if row else 0


async def get_alarms_paginated(
    page: int = 1,
    limit: int = 50,
    from_ts: Optional[int] = None,
    to_ts: Optional[int] = None,
) -> tuple[list[dict[str, Any]], int]:
    """Get paginated alarm events.

    Args:
        page: Page number (1-based).
        limit: Items per page.
        from_ts: Optional start timestamp filter.
        to_ts: Optional end timestamp filter.

    Returns:
        Tuple of (list of alarm dicts, total count).
    """
    db = await get_db()
    offset = (page - 1) * limit

    # Build WHERE clause
    conditions = []
    params: list[Any] = []

    if from_ts:
        conditions.append("created_at >= ?")
        params.append(from_ts)
    if to_ts:
        conditions.append("created_at <= ?")
        params.append(to_ts)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Get total count
    async with db.execute(
        f"SELECT COUNT(*) as count FROM alarm_event WHERE {where_clause}",
        params,
    ) as cursor:
        row = await cursor.fetchone()
        total = row["count"] if row else 0

    # Get paginated results
    async with db.execute(
        f"""
        SELECT * FROM alarm_event
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        (*params, limit, offset),
    ) as cursor:
        rows = await cursor.fetchall()
        items = [dict(row) for row in rows]

    return items, total

