"""WebSocket endpoints for edge relays and consumers."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import update
import msgpack  # type: ignore[import-untyped]

from ..core.buffer import StreamBuffer
from ..core.handlers import handle_features, handle_raw_sample
from ..core import metrics
from ..db.models import Session
from ..config import settings

logger = logging.getLogger(__name__)


async def edge_relay_endpoint(websocket: WebSocket, app):
    """Edge relay WebSocket endpoint (bidirectional).

    Flow:
    1. Accept connection
    2. Authenticate (first message)
    3. Create session
    4. Message loop (receive features/raw, send predictions/commands)
    5. Cleanup on disconnect
    """
    await websocket.accept()

    # 1. Authentication
    try:
        auth = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
    except asyncio.TimeoutError:
        await websocket.close(code=1008, reason="Authentication timeout")
        return

    api_key = auth.get("api_key")
    if api_key != settings.edge_api_key:
        await websocket.close(code=1008, reason="Invalid API key")
        return

    user_id = auth.get("user_id")
    if not user_id:
        await websocket.close(code=1008, reason="Missing user_id")
        return

    # 2. Register connection
    await app.state.connections.connect_edge(user_id, websocket)
    metrics.edge_connections.inc()

    # 3. Create session
    session_id = await create_session(app, user_id, auth.get("device_info"))
    await websocket.send_json({"type": "auth_ack", "session_id": str(session_id)})
    logger.info(f"Edge relay authenticated: {user_id}, session: {session_id}")

    metrics.sessions_created.inc()
    metrics.active_sessions.inc()

    # 4. Initialize buffer for this user
    if user_id not in app.state.buffers:
        app.state.buffers[user_id] = StreamBuffer(maxlen=settings.buffer_max_size)
        metrics.buffer_capacity.labels(user_id=user_id).set(settings.buffer_max_size)

    # 5. Message loop
    try:
        while True:
            # Handle both msgpack (binary) and JSON messages
            message = await websocket.receive()

            # Check for disconnect message
            if message.get("type") == "websocket.disconnect":
                break

            if "bytes" in message:
                data = msgpack.unpackb(message["bytes"])
            elif "text" in message:
                data = json.loads(message["text"])
            else:
                continue

            msg_type = data.get("type")

            if msg_type == "features":
                await handle_features(app, user_id, session_id, data)

            elif msg_type == "raw":
                await handle_raw_sample(app, user_id, session_id, data)

            elif msg_type == "heartbeat":
                await websocket.send_json({"type": "heartbeat_ack"})

            else:
                logger.warning(f"Unknown message type from {user_id}: {msg_type}")

    except WebSocketDisconnect:
        logger.info(f"Edge relay disconnected: {user_id}")
    except RuntimeError as e:
        if "disconnect" in str(e):
            logger.info(f"Edge relay disconnected: {user_id}")
        else:
            logger.error(f"Error in edge relay connection {user_id}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error in edge relay connection {user_id}: {e}", exc_info=True)
    finally:
        app.state.connections.disconnect_edge(user_id)
        metrics.edge_connections.dec()
        metrics.active_sessions.dec()
        metrics.sessions_ended.inc()
        await end_session(app, session_id)


async def consumer_endpoint(websocket: WebSocket, user_id: str, app):
    """Consumer WebSocket endpoint (bidirectional).

    Consumers (MCP, Azure ML, analytics) can:
    1. Subscribe to real-time features/raw samples
    2. Send predictions/commands back to edge relay

    Flow:
    1. Accept connection
    2. Subscribe to Redis channels
    3. Forward messages bidirectionally
    """
    await websocket.accept()
    consumer_id = f"consumer_{id(websocket)}"
    await app.state.connections.connect_consumer(consumer_id, websocket)

    # Subscribe to Redis channels
    pubsub = app.state.redis.pubsub()
    await pubsub.subscribe(f"user:{user_id}:features", f"user:{user_id}:raw")

    logger.info(f"Consumer {consumer_id} subscribed to user {user_id}")

    try:
        # Task 1: Forward messages from Redis to consumer
        async def forward_from_redis():
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = msgpack.unpackb(message["data"])
                    await websocket.send_json(data)

        # Task 2: Receive messages from consumer (predictions/commands)
        async def receive_from_consumer():
            while True:
                msg = await websocket.receive_json()

                if msg.get("type") == "prediction":
                    # Forward prediction to edge relay
                    success = await app.state.connections.send_to_edge(user_id, msg)

                    # Store Azure prediction to database
                    if success:
                        await app.state.persistence.add_prediction(
                            timestamp=datetime.now(timezone.utc),
                            session_id=msg.get("session_id"),
                            user_id=user_id,
                            prediction_type=msg.get("prediction_type", "azure_ml"),
                            classifier_name=msg.get("classifier_name", "azure_unknown"),
                            data=msg.get("data", {}),
                            confidence=msg.get("data", {}).get("confidence"),
                            classifier_version=msg.get("version")
                        )

        # Run both tasks concurrently (bidirectional)
        await asyncio.gather(forward_from_redis(), receive_from_consumer())

    except WebSocketDisconnect:
        logger.info(f"Consumer {consumer_id} disconnected")
    except Exception as e:
        logger.error(f"Error in consumer connection {consumer_id}: {e}", exc_info=True)
    finally:
        app.state.connections.disconnect_consumer(consumer_id)
        await pubsub.unsubscribe()


# Session management helpers

async def create_session(app, user_id: str, device_info: Optional[dict] = None) -> UUID:
    """Create a new session in database.

    Args:
        app: FastAPI app instance
        user_id: User identifier
        device_info: Device metadata (sampling_rate, channel_names, etc.)

    Returns:
        Session UUID
    """
    async with app.state.db.get_session() as session:
        sess = Session(
            user_id=user_id,
            start_time=datetime.now(timezone.utc),
            device_info=device_info
        )
        session.add(sess)
        await session.commit()
        return UUID(str(sess.session_id))


async def end_session(app, session_id: UUID):
    """End a session (set end_time).

    Args:
        app: FastAPI app instance
        session_id: Session UUID
    """
    try:
        async with app.state.db.get_session() as session:
            await session.execute(
                update(Session)
                .where(Session.session_id == session_id)
                .values(end_time=datetime.now(timezone.utc))
            )
            await session.commit()
    except Exception as e:
        logger.error(f"Error ending session {session_id}: {e}")
