#!/usr/bin/env python3
"""
Subscribe to edge relay streams in real-time.

Usage:
    python scripts/subscribe_to_stream.py <user_id> [stream_type]

Examples:
    python scripts/subscribe_to_stream.py user123 features
    python scripts/subscribe_to_stream.py user123 raw
    python scripts/subscribe_to_stream.py user123 both
"""

import asyncio
import os
import sys
from datetime import datetime

import msgpack
from redis.asyncio import Redis
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Simple settings class
class Settings:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    enable_redis_pubsub = os.getenv("ENABLE_REDIS_PUBSUB", "true").lower() == "true"

settings = Settings()


async def subscribe_to_features(redis: Redis, user_id: str):
    """Subscribe to features stream."""
    channel = f"user:{user_id}:features"
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    print(f"📊 Subscribed to features stream: {channel}")
    print("Waiting for messages... (Ctrl+C to stop)\n")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = msgpack.unpackb(message["data"], raw=False)
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

                print(f"[{timestamp}] FEATURES:")
                print(f"  Workload: {data.get('workload', 'N/A')}")
                print(f"  Confidence: {data.get('confidence', 'N/A'):.2%}")

                if "features" in data:
                    print(f"  Features:")
                    for key, value in data["features"].items():
                        print(f"    {key}: {value:.3f}")
                print()

    except KeyboardInterrupt:
        print("\n\nStopping features subscriber...")
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()


async def subscribe_to_raw(redis: Redis, user_id: str):
    """Subscribe to raw EEG samples stream."""
    channel = f"user:{user_id}:raw"
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    print(f"🧠 Subscribed to raw EEG stream: {channel}")
    print("Waiting for messages... (Ctrl+C to stop)\n")

    sample_count = 0

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = msgpack.unpackb(message["data"], raw=False)
                sample_count += 1
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

                print(f"[{timestamp}] RAW SAMPLE #{sample_count}:")

                if "channels" in data:
                    print(f"  Channels:")
                    for channel_name, value in data["channels"].items():
                        print(f"    {channel_name}: {value:>8.3f} µV")

                if "sample_number" in data:
                    print(f"  Sample #: {data['sample_number']}")

                print()

    except KeyboardInterrupt:
        print(f"\n\nStopping raw subscriber... (received {sample_count} samples)")
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()


async def subscribe_to_both(redis: Redis, user_id: str):
    """Subscribe to both features and raw streams."""
    features_channel = f"user:{user_id}:features"
    raw_channel = f"user:{user_id}:raw"

    pubsub = redis.pubsub()
    await pubsub.subscribe(features_channel, raw_channel)

    print(f"📊🧠 Subscribed to both streams for user: {user_id}")
    print(f"  - Features: {features_channel}")
    print(f"  - Raw: {raw_channel}")
    print("Waiting for messages... (Ctrl+C to stop)\n")

    sample_count = 0

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                channel = message["channel"].decode()
                data = msgpack.unpackb(message["data"], raw=False)
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

                if "features" in channel:
                    print(f"[{timestamp}] 📊 FEATURES:")
                    print(f"  Workload: {data.get('workload', 'N/A')}")
                    print(f"  Confidence: {data.get('confidence', 'N/A'):.2%}")
                else:
                    sample_count += 1
                    print(f"[{timestamp}] 🧠 RAW SAMPLE #{sample_count}")
                    if "channels" in data:
                        # Show first 4 channels only
                        channels = list(data["channels"].items())[:4]
                        print(f"  {', '.join([f'{k}:{v:.2f}' for k, v in channels])}")

                print()

    except KeyboardInterrupt:
        print(f"\n\nStopping subscriber... (received {sample_count} raw samples)")
    finally:
        await pubsub.unsubscribe(features_channel, raw_channel)
        await pubsub.aclose()


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/subscribe_to_stream.py <user_id> [stream_type]")
        print("\nStream types:")
        print("  features - Subscribe to features stream only")
        print("  raw      - Subscribe to raw EEG stream only")
        print("  both     - Subscribe to both streams (default)")
        print("\nExample:")
        print("  python scripts/subscribe_to_stream.py user123 features")
        sys.exit(1)

    user_id = sys.argv[1]
    stream_type = sys.argv[2].lower() if len(sys.argv) > 2 else "both"

    if stream_type not in ["features", "raw", "both"]:
        print(f"Error: Invalid stream type '{stream_type}'")
        print("Valid options: features, raw, both")
        sys.exit(1)

    # Check if Redis pub/sub is enabled
    if not settings.enable_redis_pubsub:
        print("⚠️  WARNING: Redis pub/sub is disabled in settings!")
        print("Set ENABLE_REDIS_PUBSUB=true to enable broadcasting")
        sys.exit(1)

    # Connect to Redis
    print(f"Connecting to Redis: {settings.redis_url}")
    redis = Redis.from_url(settings.redis_url, decode_responses=False)

    try:
        # Test connection
        await redis.ping()
        print("✓ Connected to Redis\n")

        # Subscribe based on type
        if stream_type == "features":
            await subscribe_to_features(redis, user_id)
        elif stream_type == "raw":
            await subscribe_to_raw(redis, user_id)
        else:  # both
            await subscribe_to_both(redis, user_id)

    except ConnectionError as e:
        print(f"❌ Failed to connect to Redis: {e}")
        print(f"Make sure Redis is running at: {settings.redis_url}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    finally:
        await redis.aclose()
        print("\nDisconnected from Redis")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nExiting...")
