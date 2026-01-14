"""RFID Edge Service - FastAPI Application Entry Point.

Main application setup with all routes, middleware, and lifecycle management.
"""

import asyncio
import logging
import sys
import time
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import get_app_dir, get_config, get_settings, load_config
from database import close_db, get_alarms_count_24h, get_tag_counts, init_db
from models import HealthResponse, StatsResponse
from mqtt_client import get_mqtt_client
from routers import alarms, calibration, config_router, tags
from services.ttl_cleanup import start_cleanup_service, stop_cleanup_service, is_cleanup_running
from services.websocket_manager import get_ws_manager

# Configure logging
settings = get_settings()

# Create logs directory in app directory (writable location)
log_dir = get_app_dir() / "logs"
log_dir.mkdir(exist_ok=True)

# Configure log file path
log_file = log_dir / "edge-service.log"

# Setup logging handlers
handlers = [
    logging.StreamHandler(sys.stdout),
    RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,  # Keep 5 backup files
        encoding="utf-8",
    ),
]

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=handlers,
)
logger = logging.getLogger(__name__)
logger.info(f"Logging to file: {log_file}")

# Application start time for uptime calculation
_start_time: float = 0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown of all services.
    """
    global _start_time
    _start_time = time.time()

    logger.info("Starting RFID Edge Service...")

    # Load configuration
    load_config()
    config = get_config()
    logger.info(f"Configuration loaded: gate_id={config.gate.client_id}")

    # Initialize database
    await init_db()

    # Connect MQTT client
    mqtt = get_mqtt_client()
    loop = asyncio.get_event_loop()
    mqtt.connect(loop)

    # Start TTL cleanup service
    start_cleanup_service()

    # Start WebSocket status updates
    ws_manager = get_ws_manager()
    ws_manager.start_status_updates(lambda: mqtt.is_connected)

    logger.info("RFID Edge Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down RFID Edge Service...")

    # Stop services
    await ws_manager.stop_status_updates()
    await stop_cleanup_service()
    mqtt.disconnect()
    await close_db()

    logger.info("RFID Edge Service stopped")


# Create FastAPI application
app = FastAPI(
    title="RFID Edge Service",
    description="RFID Security Gate Edge Service for pharmacy retail chains",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(tags.router)
app.include_router(config_router.router)
app.include_router(calibration.router)
app.include_router(alarms.router)


# Health check endpoint
@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns service status including MQTT connection and database health.
    """
    mqtt = get_mqtt_client()
    uptime = int(time.time() - _start_time) if _start_time > 0 else 0

    # Check database by running a simple query
    db_ok = True
    try:
        await get_tag_counts()
    except Exception:
        db_ok = False

    return HealthResponse(
        ok=mqtt.is_connected and db_ok,
        mqtt_connected=mqtt.is_connected,
        db_ok=db_ok,
        gate_last_seen_seconds=mqtt.last_tag_seen_seconds,
        uptime_seconds=uptime,
    )


# Statistics endpoint
@app.get("/v1/stats", response_model=StatsResponse, tags=["stats"])
async def get_stats() -> StatsResponse:
    """Get service statistics.

    Returns counts of tags by state and recent alarm count.
    """
    counts = await get_tag_counts()
    alarms_24h = await get_alarms_count_24h()

    return StatsResponse(
        in_cart_count=counts["in_cart_count"],
        paid_count=counts["paid_count"],
        alarms_last_24h=alarms_24h,
    )


# Debug endpoint for TTL cleanup status
@app.get("/v1/debug/cleanup", tags=["debug"])
async def get_cleanup_status() -> dict:
    """Get TTL cleanup service status (debug endpoint).

    Returns cleanup task status and current TTL configuration.
    """
    config = get_config()
    return {
        "cleanup_running": is_cleanup_running(),
        "cleanup_interval_seconds": config.ttl.cleanup_interval_seconds,
        "in_cart_ttl_seconds": config.ttl.in_cart_seconds,
        "paid_ttl_seconds": config.ttl.paid_seconds,
    }


# Debug endpoint for viewing logs
@app.get("/v1/debug/logs", tags=["debug"])
async def get_logs(lines: int = 100) -> dict:
    """Get recent log entries (debug endpoint).

    Args:
        lines: Number of recent lines to return (default 100, max 500).

    Returns:
        Dict with log file path and recent log lines.
    """
    lines = min(lines, 500)  # Limit to 500 lines max

    log_path = get_app_dir() / "logs" / "edge-service.log"

    if not log_path.exists():
        return {"log_path": str(log_path), "exists": False, "lines": []}

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return {
                "log_path": str(log_path),
                "exists": True,
                "total_lines": len(all_lines),
                "lines": [line.rstrip() for line in recent_lines],
            }
    except Exception as e:
        return {"log_path": str(log_path), "exists": True, "error": str(e), "lines": []}


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time events.

    Clients receive TAG_DETECTED, ALARM_TRIGGERED, and STATUS_UPDATE events.
    """
    ws_manager = get_ws_manager()
    await ws_manager.connect(websocket)

    try:
        while True:
            # Keep connection alive, handle any client messages
            data = await websocket.receive_text()
            logger.debug(f"WebSocket received: {data}")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)



# Mount static files for frontend (if exists)
# Handle PyInstaller bundled paths
def get_static_path() -> Path:
    """Get the correct static files path, handling PyInstaller bundles."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        base_path = Path(sys._MEIPASS)  # type: ignore
    else:
        # Running as normal Python script
        base_path = Path(__file__).parent.parent
    return base_path / "static"

static_path = get_static_path()
logger.info(f"Looking for static files at: {static_path}")
if static_path.exists():
    logger.info(f"Mounting static files from: {static_path}")
    app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static")
else:
    logger.warning(f"Static files not found at: {static_path}")

if __name__ == "__main__":
    import uvicorn

    config = get_config()
    uvicorn.run(
        app,
        host=config.http.host,
        port=config.http.port,
    )

