"""Message handlers for edge relay messages."""

import logging
from datetime import datetime, timezone
from uuid import UUID

import msgpack  # type: ignore[import-untyped]

from . import metrics
from ..config import settings

logger = logging.getLogger(__name__)


async def handle_features(app, user_id: str, session_id: UUID, data: dict):
    """Process incoming features from edge relay.

    Features are:
    1. Added to buffer (in-memory for instant queries)
    2. Published to Redis (broadcast to consumers)
    3. Queued for database (batched writes)
    """
    timestamp = datetime.now(timezone.utc)

    # Track message received
    metrics.messages_received.labels(message_type="features", user_id=user_id).inc()

    try:
        # 1. Add to buffer
        await app.state.buffers[user_id].add_sample(
            timestamp=timestamp,
            data=data,
            session_id=session_id,
            user_id=user_id,
            sample_type="features"
        )

        # Update buffer metrics
        stats = await app.state.buffers[user_id].get_stats()
        metrics.buffer_size.labels(user_id=user_id).set(stats["total_samples"])

        # 2. Publish to Redis (broadcast) - optional
        if settings.enable_redis_pubsub:
            try:
                await app.state.redis.publish(
                    f"user:{user_id}:features",
                    msgpack.packb(data)
                )
            except Exception as e:
                logger.error(f"Redis publish error: {e}")

        # 3. Queue for database (batched) - optional
        if settings.enable_database_persistence:
            await app.state.persistence.add_prediction(
                timestamp=timestamp,
                session_id=session_id,
                user_id=user_id,
                prediction_type="workload_edge",
                classifier_name="edge_relay",
                data=data,
                confidence=data.get("confidence")
            )

        # Track successful processing
        metrics.messages_processed.labels(message_type="features").inc()

    except Exception as e:
        metrics.messages_failed.labels(message_type="features", error_type=type(e).__name__).inc()
        raise


async def handle_raw_sample(app, user_id: str, session_id: UUID, data: dict):
    """Process incoming raw EEG sample from edge relay.

    Raw samples are:
    1. Added to buffer (for visualization/queries)
    2. Published to Redis (for consumers that need raw EEG)
    3. Queued for database (if enabled - high volume!)
    """
    timestamp = datetime.now(timezone.utc)

    # Track message received
    metrics.messages_received.labels(message_type="raw", user_id=user_id).inc()

    try:
        # 1. Add to buffer
        await app.state.buffers[user_id].add_sample(
            timestamp=timestamp,
            data=data,
            session_id=session_id,
            user_id=user_id,
            sample_type="raw"
        )

        # 2. Publish to Redis - optional
        if settings.enable_redis_pubsub:
            try:
                await app.state.redis.publish(
                    f"user:{user_id}:raw",
                    msgpack.packb(data)
                )
            except Exception as e:
                logger.error(f"Redis publish error: {e}")

        # 3. Queue for database - optional
        if settings.enable_database_persistence:
            await app.state.persistence.add_raw_sample(
                timestamp=timestamp,
                session_id=session_id,
                user_id=user_id,
                data=data
            )

        # Track successful processing
        metrics.messages_processed.labels(message_type="raw").inc()

    except Exception as e:
        metrics.messages_failed.labels(message_type="raw", error_type=type(e).__name__).inc()
        raise
