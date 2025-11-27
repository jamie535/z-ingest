"""Zander Ingestion Server - Main FastAPI application.

Lightweight bidirectional WebSocket broker for EEG data streams.
Receives features/raw EEG from edge relays, broadcasts to multiple consumers (MCP, Azure ML, analytics).
"""

import logging
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, WebSocket, Response
import redis.asyncio as redis
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from prometheus_fastapi_instrumentator import Instrumentator

from .config import settings
from .core.connections import ConnectionManager
from .core.buffer import StreamBuffer
from .db.persistence import PersistenceManager
from .db.database import DatabaseManager
from .api.rest import router as rest_router
from .api.websocket import edge_relay_endpoint, consumer_endpoint
from .core import metrics

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management (startup/shutdown)."""
    logger.info("Starting Zander Ingestion Server...")

    # Set application info for Prometheus
    metrics.app_info.info({
        "version": "0.1.0",
        "environment": "production" if settings.log_level == "INFO" else "development"
    })

    # Initialize services
    app.state.connections = ConnectionManager()
    buffers: Dict[str, StreamBuffer] = {}
    app.state.buffers = buffers  # user_id -> StreamBuffer
    app.state.redis = await redis.from_url(settings.redis_url)
    app.state.db = DatabaseManager(settings.database_url)

    # Initialize database schema
    try:
        await app.state.db.initialize()
    except Exception as e:
        logger.warning(f"Database initialization warning (may already exist): {e}")

    # Initialize persistence manager
    app.state.persistence = PersistenceManager(
        app.state.db,
        batch_size=settings.batch_size,
        flush_interval=settings.flush_interval
    )
    await app.state.persistence.start()

    logger.info("Zander Ingestion Server started successfully")
    logger.info("  - WebSocket endpoint: /stream (edge relays)")
    logger.info("  - Subscribe endpoint: /subscribe/{user_id} (consumers)")
    logger.info("  - Health check: /health")
    logger.info("  - Metrics endpoint: /metrics")

    yield

    # Shutdown
    logger.info("Shutting down Zander Ingestion Server...")
    await app.state.persistence.stop()
    await app.state.redis.close()
    await app.state.db.close()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Zander Ingestion Server",
    description="Lightweight bidirectional WebSocket broker for EEG data streams",
    version="0.1.0",
    lifespan=lifespan
)

# Initialize Prometheus instrumentation
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# Include REST routes
app.include_router(rest_router)


@app.get("/metrics-custom")
async def metrics_custom():
    """Custom metrics endpoint (Prometheus format)."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# WebSocket routes
@app.websocket("/stream")
async def stream_endpoint(websocket: WebSocket):
    """Edge relay WebSocket endpoint."""
    await edge_relay_endpoint(websocket, app)


@app.websocket("/subscribe/{user_id}")
async def subscribe_endpoint(websocket: WebSocket, user_id: str):
    """Consumer WebSocket endpoint."""
    await consumer_endpoint(websocket, user_id, app)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
