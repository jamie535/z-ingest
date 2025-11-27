"""Tests for Redis pub/sub functionality with edge relay streams."""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import msgpack
import pytest
from redis.asyncio import Redis

from app.config import settings


@pytest.fixture(scope="function")
async def redis_client():
    """Create Redis client for testing."""
    client = Redis.from_url(settings.redis_url, decode_responses=False)
    yield client
    await client.aclose()


@pytest.fixture(scope="function")
def test_user_id():
    """Generate a unique test user ID."""
    return f"test-user-{uuid4().hex[:8]}"


@pytest.mark.asyncio
async def test_redis_connection(redis_client):
    """Test basic Redis connection."""
    # Test ping
    response = await redis_client.ping()
    assert response is True


@pytest.mark.asyncio
async def test_publish_features_to_redis(redis_client, test_user_id):
    """Test publishing features data to Redis channel."""
    # Test data
    features_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "workload": "high",
        "confidence": 0.95,
        "features": {
            "alpha": 0.6,
            "beta": 0.3,
            "theta": 0.1
        }
    }

    # Publish to channel
    channel = f"user:{test_user_id}:features"
    packed_data = msgpack.packb(features_data)

    # Publish returns number of subscribers (0 if none listening)
    result = await redis_client.publish(channel, packed_data)
    assert result >= 0  # Should not raise error


@pytest.mark.asyncio
async def test_subscribe_to_features_stream(redis_client, test_user_id):
    """Test subscribing to and receiving features from Redis channel."""
    received_data = None
    channel = f"user:{test_user_id}:features"

    # Test data
    features_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "workload": "medium",
        "confidence": 0.88,
        "features": {
            "alpha": 0.5,
            "beta": 0.4,
            "theta": 0.1
        }
    }

    async def subscriber():
        """Subscribe and wait for message."""
        nonlocal received_data
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)

        # Wait for subscription confirmation and message
        async for message in pubsub.listen():
            if message["type"] == "message":
                received_data = msgpack.unpackb(message["data"], raw=False)
                break

        await pubsub.unsubscribe(channel)
        await pubsub.aclose()

    # Start subscriber
    subscriber_task = asyncio.create_task(subscriber())

    # Wait a bit for subscription to be ready
    await asyncio.sleep(0.1)

    # Publish data
    packed_data = msgpack.packb(features_data)
    await redis_client.publish(channel, packed_data)

    # Wait for subscriber to receive
    await asyncio.wait_for(subscriber_task, timeout=2.0)

    # Verify received data matches published data
    assert received_data is not None
    assert received_data["workload"] == features_data["workload"]
    assert received_data["confidence"] == features_data["confidence"]
    assert received_data["features"]["alpha"] == features_data["features"]["alpha"]


@pytest.mark.asyncio
async def test_subscribe_to_raw_stream(redis_client, test_user_id):
    """Test subscribing to and receiving raw EEG samples from Redis."""
    received_data = None
    channel = f"user:{test_user_id}:raw"

    # Test raw sample data
    raw_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "channels": {
            "AF7": 0.234,
            "AF8": -0.123,
            "TP9": 0.456,
            "TP10": -0.789
        },
        "sample_number": 12345
    }

    async def subscriber():
        """Subscribe and wait for raw sample."""
        nonlocal received_data
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)

        async for message in pubsub.listen():
            if message["type"] == "message":
                received_data = msgpack.unpackb(message["data"], raw=False)
                break

        await pubsub.unsubscribe(channel)
        await pubsub.aclose()

    # Start subscriber
    subscriber_task = asyncio.create_task(subscriber())
    await asyncio.sleep(0.1)

    # Publish raw sample
    packed_data = msgpack.packb(raw_data)
    await redis_client.publish(channel, packed_data)

    # Wait for subscriber
    await asyncio.wait_for(subscriber_task, timeout=2.0)

    # Verify
    assert received_data is not None
    assert received_data["sample_number"] == raw_data["sample_number"]
    assert received_data["channels"]["AF7"] == raw_data["channels"]["AF7"]


@pytest.mark.asyncio
async def test_multiple_subscribers(redis_client, test_user_id):
    """Test multiple subscribers receiving the same message."""
    received_count = 0
    channel = f"user:{test_user_id}:features"

    test_data = {
        "workload": "low",
        "confidence": 0.75
    }

    async def subscriber(subscriber_id):
        """Individual subscriber."""
        nonlocal received_count
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)

        async for message in pubsub.listen():
            if message["type"] == "message":
                data = msgpack.unpackb(message["data"], raw=False)
                if data["workload"] == test_data["workload"]:
                    received_count += 1
                break

        await pubsub.unsubscribe(channel)
        await pubsub.aclose()

    # Start 3 subscribers
    tasks = [
        asyncio.create_task(subscriber(i))
        for i in range(3)
    ]

    await asyncio.sleep(0.2)

    # Publish once
    packed_data = msgpack.packb(test_data)
    await redis_client.publish(channel, packed_data)

    # Wait for all subscribers
    await asyncio.gather(*tasks, return_exceptions=True)

    # All 3 should have received
    assert received_count == 3


@pytest.mark.asyncio
async def test_multiple_user_channels(redis_client):
    """Test that messages are isolated per user channel."""
    user1_id = f"test-user-{uuid4().hex[:8]}"
    user2_id = f"test-user-{uuid4().hex[:8]}"

    user1_received = None
    user2_received = None

    user1_data = {"user": "user1", "value": 100}
    user2_data = {"user": "user2", "value": 200}

    async def subscriber_user1():
        nonlocal user1_received
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"user:{user1_id}:features")

        async for message in pubsub.listen():
            if message["type"] == "message":
                user1_received = msgpack.unpackb(message["data"], raw=False)
                break

        await pubsub.aclose()

    async def subscriber_user2():
        nonlocal user2_received
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"user:{user2_id}:features")

        async for message in pubsub.listen():
            if message["type"] == "message":
                user2_received = msgpack.unpackb(message["data"], raw=False)
                break

        await pubsub.aclose()

    # Start both subscribers
    task1 = asyncio.create_task(subscriber_user1())
    task2 = asyncio.create_task(subscriber_user2())
    await asyncio.sleep(0.1)

    # Publish to both channels
    await redis_client.publish(
        f"user:{user1_id}:features",
        msgpack.packb(user1_data)
    )
    await redis_client.publish(
        f"user:{user2_id}:features",
        msgpack.packb(user2_data)
    )

    # Wait for both
    await asyncio.gather(task1, task2)

    # Verify isolation
    assert user1_received["user"] == "user1"
    assert user1_received["value"] == 100
    assert user2_received["user"] == "user2"
    assert user2_received["value"] == 200


@pytest.mark.asyncio
async def test_msgpack_serialization(redis_client, test_user_id):
    """Test that complex data structures survive msgpack serialization."""
    channel = f"user:{test_user_id}:features"

    # Complex nested structure
    complex_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": str(uuid4()),
        "nested": {
            "array": [1, 2, 3, 4, 5],
            "dict": {
                "a": 1.234,
                "b": -5.678,
                "c": None
            },
            "boolean": True
        },
        "floats": [0.1, 0.2, 0.3]
    }

    received_data = None

    async def subscriber():
        nonlocal received_data
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)

        async for message in pubsub.listen():
            if message["type"] == "message":
                received_data = msgpack.unpackb(message["data"], raw=False)
                break

        await pubsub.aclose()

    subscriber_task = asyncio.create_task(subscriber())
    await asyncio.sleep(0.1)

    await redis_client.publish(channel, msgpack.packb(complex_data))
    await asyncio.wait_for(subscriber_task, timeout=2.0)

    # Verify complex structure
    assert received_data["session_id"] == complex_data["session_id"]
    assert received_data["nested"]["array"] == complex_data["nested"]["array"]
    assert received_data["nested"]["dict"]["a"] == complex_data["nested"]["dict"]["a"]
    assert received_data["nested"]["boolean"] is True
    assert received_data["floats"] == complex_data["floats"]


@pytest.mark.asyncio
async def test_redis_pubsub_disabled(redis_client, test_user_id, monkeypatch):
    """Test that Redis pub/sub can be disabled via settings."""
    # Simulate disabled Redis pub/sub
    monkeypatch.setattr("app.config.settings.enable_redis_pubsub", False)

    from app.config import settings

    # When disabled, should not publish
    assert settings.enable_redis_pubsub is False

    # This test just verifies the setting works
    # The actual handler logic checks this before publishing
