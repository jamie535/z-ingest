#!/usr/bin/env python3
"""
Test script for consumer sending predictions back to edge relay.

This script connects as a consumer, receives data, and sends test predictions back.

Usage:
    python scripts/test_consumer_predictions.py <user_id> <server_url>

Example:
    python scripts/test_consumer_predictions.py jamie_123 wss://jubilant-warmth-production.up.railway.app
"""

import asyncio
import json
import sys
from datetime import datetime

import websockets
import msgpack


async def test_consumer(user_id: str, server_url: str):
    """
    Connect as a consumer and send test predictions back.

    Args:
        user_id: User ID to subscribe to
        server_url: WebSocket server URL (e.g., wss://server.com)
    """
    # Build subscribe endpoint
    subscribe_url = f"{server_url}/subscribe/{user_id}"

    print(f"🔗 Connecting to: {subscribe_url}")
    print(f"📡 Subscribing to user: {user_id}")
    print("-" * 60)

    try:
        async with websockets.connect(subscribe_url) as ws:
            print("✅ Connected successfully!")
            print("📥 Waiting for data from edge relay...\n")

            message_count = 0

            # Task 1: Receive data from edge relay
            async def receive_data():
                nonlocal message_count
                async for message in ws:
                    try:
                        data = json.loads(message)
                        message_count += 1

                        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        msg_type = data.get("type", "unknown")

                        print(f"[{timestamp}] 📩 Received #{message_count} - Type: {msg_type}")

                        if msg_type == "features":
                            print(f"  └─ Workload: {data.get('workload', 'N/A')}")
                        elif msg_type == "raw":
                            channels = data.get("channels", {})
                            print(f"  └─ Channels: {len(channels)}")

                    except json.JSONDecodeError as e:
                        print(f"❌ Failed to parse message: {e}")

            # Task 2: Send test predictions back every 5 seconds
            async def send_predictions():
                await asyncio.sleep(2)  # Wait 2 seconds before first prediction

                prediction_count = 0

                while True:
                    prediction_count += 1
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

                    # Send test prediction
                    prediction = {
                        "type": "prediction",
                        "prediction_type": "workload",
                        "data": {
                            "workload": 0.75 + (prediction_count * 0.05) % 0.3,  # Varying value
                            "confidence": 0.92,
                            "test_prediction_number": prediction_count
                        },
                        "confidence": 0.92,
                        "source": "test_script",
                        "timestamp": datetime.utcnow().isoformat()
                    }

                    await ws.send(json.dumps(prediction))
                    print(f"[{timestamp}] 📤 Sent prediction #{prediction_count}")
                    print(f"  └─ Workload: {prediction['data']['workload']:.2f}")
                    print(f"  └─ Confidence: {prediction['confidence']:.2%}\n")

                    await asyncio.sleep(5)  # Send prediction every 5 seconds

            # Run both tasks concurrently
            await asyncio.gather(
                receive_data(),
                send_predictions()
            )

    except websockets.exceptions.WebSocketException as e:
        print(f"\n❌ WebSocket error: {e}")
        print("\nTroubleshooting:")
        print("  1. Check that the server URL is correct")
        print("  2. Ensure the edge relay is connected and sending data")
        print("  3. Verify network connectivity")
    except KeyboardInterrupt:
        print(f"\n\n✋ Stopped by user")
        print(f"📊 Statistics:")
        print(f"  - Messages received: {message_count}")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        raise


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: python scripts/test_consumer_predictions.py <user_id> <server_url>")
        print("\nExamples:")
        print("  python scripts/test_consumer_predictions.py jamie_123 wss://jubilant-warmth-production.up.railway.app")
        print("  python scripts/test_consumer_predictions.py jamie_123 ws://localhost:8000")
        sys.exit(1)

    user_id = sys.argv[1]
    server_url = sys.argv[2].rstrip('/')  # Remove trailing slash

    # Validate server URL
    if not server_url.startswith(('ws://', 'wss://')):
        print(f"❌ Error: Server URL must start with ws:// or wss://")
        print(f"Got: {server_url}")
        sys.exit(1)

    try:
        asyncio.run(test_consumer(user_id, server_url))
    except KeyboardInterrupt:
        print("\n\nExiting...")


if __name__ == "__main__":
    main()
