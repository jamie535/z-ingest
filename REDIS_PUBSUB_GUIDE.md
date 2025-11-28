# Redis Pub/Sub Communication Guide

## Overview

The ingestion server uses Redis pub/sub for real-time, bidirectional communication between edge relays and consumers. This is simpler, faster, and more flexible than WebSocket routing.

## Architecture

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   Edge Relay    │         │ Ingestion Server│         │   Consumer      │
│  (Your Device)  │         │    + Redis      │         │ (Colleague/ML)  │
└─────────────────┘         └─────────────────┘         └─────────────────┘
        │                            │                            │
        │ Publish: user:jamie:raw    │                            │
        ├───────────────────────────>│                            │
        │                            │ Subscribe: user:jamie:raw  │
        │                            │<───────────────────────────┤
        │                            │ Forward via Redis          │
        │                            ├───────────────────────────>│
        │                            │                            │
        │                            │ Publish: user:jamie:predictions
        │                            │<───────────────────────────┤
        │ Subscribe: user:jamie:predictions                       │
        │<───────────────────────────┤                            │
```

## Redis Channels

### Standard Channels (Already Implemented)

| Channel | Publisher | Subscriber | Data Type | Purpose |
|---------|-----------|------------|-----------|---------|
| `user:{user_id}:features` | Edge Relay | Consumers | Features | Processed workload metrics |
| `user:{user_id}:raw` | Edge Relay | Consumers | Raw EEG | Raw channel data |

### Bidirectional Channels (For Predictions)

| Channel | Publisher | Subscriber | Data Type | Purpose |
|---------|-----------|------------|-----------|---------|
| `user:{user_id}:predictions` | Consumer | Edge Relay | Predictions | ML predictions sent back |
| `user:{user_id}:commands` | Consumer | Edge Relay | Commands | Control commands (optional) |
| `user:{user_id}:alerts` | Consumer | Edge Relay | Alerts | System alerts (optional) |

## Current Implementation Status

✅ **Working:**
- Edge relay publishes features/raw to Redis (app/core/handlers.py:39-47)
- Consumers can subscribe to features/raw (scripts/subscribe_to_stream.py)
- Tests verify Redis pub/sub works (tests/test_redis_pubsub.py)

❌ **Not Implemented:**
- Edge relay subscribing to predictions channel
- Consumers publishing predictions back
- Ingestion server doesn't forward predictions via Redis (uses WebSocket instead)

## Use Cases

### Use Case 1: Your Colleague Processes Your EEG Data

**You (Edge Relay):**
1. Publish raw EEG to `user:jamie:raw`
2. Subscribe to `user:jamie:predictions`
3. Receive predictions and display on screen

**Your Colleague (Consumer):**
1. Subscribe to `user:jamie:raw`
2. Process with ML model
3. Publish predictions to `user:jamie:predictions`

**No ingestion server code needed!** Pure Redis pub/sub.

### Use Case 2: Azure ML Batch Processing

**Edge Relay:**
1. Publish features to `user:jamie:features`

**Azure Function:**
1. Subscribe to `user:jamie:features`
2. Batch process every 5 seconds
3. Publish predictions to `user:jamie:predictions`

**Edge Relay:**
1. Subscribe to `user:jamie:predictions`
2. Display results

### Use Case 3: Multiple Consumers

**Edge Relay:**
- Publishes to `user:jamie:raw`

**Consumer A (MCP Server):**
- Subscribes to `user:jamie:raw`
- Logs data to file

**Consumer B (Azure ML):**
- Subscribes to `user:jamie:raw`
- Publishes predictions to `user:jamie:predictions`

**Consumer C (Dashboard):**
- Subscribes to `user:jamie:raw` AND `user:jamie:predictions`
- Shows real-time data + predictions

## Implementation Examples

### Edge Relay: Send and Receive (Python)

```python
import asyncio
import msgpack
from redis.asyncio import Redis
from pylsl import StreamInlet, resolve_stream

async def edge_relay_bidirectional(user_id: str):
    """
    Edge relay that sends EEG data and receives predictions.
    """
    redis = Redis.from_url("redis://localhost:6379", decode_responses=False)

    # Subscribe to predictions channel
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"user:{user_id}:predictions")

    print(f"✓ Subscribed to predictions for {user_id}")

    # Resolve LSL stream
    print("Looking for EEG stream...")
    streams = resolve_stream('type', 'EEG')
    inlet = StreamInlet(streams[0])

    # Task 1: Publish EEG samples
    async def publish_eeg():
        while True:
            sample, timestamp = inlet.pull_sample(timeout=1.0)
            if sample:
                data = {
                    "type": "raw",
                    "timestamp": timestamp,
                    "channels": {f"Ch{i}": v for i, v in enumerate(sample)}
                }

                # Publish to Redis
                await redis.publish(
                    f"user:{user_id}:raw",
                    msgpack.packb(data)
                )

            await asyncio.sleep(0.01)  # 100 Hz

    # Task 2: Receive predictions
    async def receive_predictions():
        async for message in pubsub.listen():
            if message["type"] == "message":
                prediction = msgpack.unpackb(message["data"])

                print(f"\n🔮 PREDICTION RECEIVED:")
                print(f"  Type: {prediction.get('prediction_type')}")
                print(f"  Data: {prediction.get('data')}")
                print(f"  Confidence: {prediction.get('confidence', 0):.2%}")

                # TODO: Display on screen, trigger alerts, etc.

    # Run both tasks concurrently
    try:
        await asyncio.gather(
            publish_eeg(),
            receive_predictions()
        )
    finally:
        await pubsub.unsubscribe()
        await redis.aclose()

# Run
asyncio.run(edge_relay_bidirectional("jamie"))
```

### Consumer: Receive and Send (Python)

```python
import asyncio
import msgpack
import numpy as np
from redis.asyncio import Redis

async def consumer_with_predictions(user_id: str, ml_model):
    """
    Consumer that receives EEG data and sends predictions back.
    """
    redis = Redis.from_url("redis://localhost:6379", decode_responses=False)

    # Subscribe to raw EEG
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"user:{user_id}:raw")

    print(f"✓ Subscribed to raw EEG for {user_id}")

    buffer = []

    async for message in pubsub.listen():
        if message["type"] == "message":
            data = msgpack.unpackb(message["data"])

            # Collect samples
            channels = data.get("channels", {})
            buffer.append(list(channels.values()))

            # Process every 100 samples (~1 second at 100 Hz)
            if len(buffer) >= 100:
                # Run ML prediction
                features = np.array(buffer)
                prediction = ml_model.predict(features)

                # Publish prediction back
                prediction_data = {
                    "type": "prediction",
                    "prediction_type": "workload",
                    "data": {
                        "workload": float(prediction[0]),
                        "valence": float(prediction[1]),
                        "arousal": float(prediction[2])
                    },
                    "confidence": 0.92,
                    "source": "azure_ml_v1",
                    "timestamp": data.get("timestamp")
                }

                await redis.publish(
                    f"user:{user_id}:predictions",
                    msgpack.packb(prediction_data)
                )

                print(f"✓ Sent prediction: workload={prediction[0]:.2f}")

                # Clear buffer
                buffer = []

    await pubsub.unsubscribe()
    await redis.aclose()

# Run
import joblib
model = joblib.load("my_ml_model.pkl")
asyncio.run(consumer_with_predictions("jamie", model))
```

### Consumer: Receive Only (Simple)

```python
# If you just want to subscribe (already have this!)
python scripts/subscribe_to_stream.py jamie raw
```

## Testing

### Test 1: Subscribe to Your Own Stream

```bash
# Terminal 1: Run ingestion server
python -m app.main

# Terminal 2: Run your edge relay (send EEG data)
# (your edge relay code here)

# Terminal 3: Subscribe to your stream
python scripts/subscribe_to_stream.py jamie raw
```

### Test 2: Bidirectional with Redis CLI

```bash
# Terminal 1: Subscribe to predictions (simulate edge relay receiving)
redis-cli
> SUBSCRIBE user:jamie:predictions

# Terminal 2: Publish a prediction (simulate consumer sending)
redis-cli
> PUBLISH user:jamie:predictions '{"type":"prediction","data":{"workload":0.85}}'

# Terminal 1 should show the message!
```

### Test 3: Run pytest

```bash
pytest tests/test_redis_pubsub.py -v
```

## Advantages of Redis Pub/Sub vs WebSockets

| Aspect | Redis Pub/Sub | WebSockets |
|--------|---------------|------------|
| **Latency** | 1-5ms | 10-50ms |
| **Architecture** | Decoupled | Coupled to server |
| **Consumer code** | Simple subscribe/publish | Bidirectional WebSocket handling |
| **Edge relay code** | Simple subscribe/publish | Need to handle incoming WebSocket messages |
| **Multiple consumers** | Native support | Need routing logic |
| **Reconnection** | Built-in | Manual handling |
| **Already implemented** | ✅ Yes (for data) | ✅ Yes (but complex) |

## What's Missing vs What Exists

### Already Working ✅

1. **Edge relay publishes to Redis** (app/core/handlers.py:39-47)
   ```python
   await app.state.redis.publish(
       f"user:{user_id}:features",
       msgpack.packb(data)
   )
   ```

2. **Consumer subscribes via script** (scripts/subscribe_to_stream.py)
   ```bash
   python scripts/subscribe_to_stream.py jamie raw
   ```

3. **Tests verify Redis works** (tests/test_redis_pubsub.py)
   ```bash
   pytest tests/test_redis_pubsub.py -v
   # All 8 tests pass ✅
   ```

### Not Implemented ❌

1. **Edge relay subscribing to predictions**
   - Your edge relay code doesn't subscribe to `user:jamie:predictions`
   - Need to add this to your edge relay client

2. **Consumer publishing predictions**
   - `scripts/subscribe_to_stream.py` is read-only
   - Need to add `redis.publish()` after processing

3. **Ingestion server forwarding predictions via Redis**
   - Currently uses WebSocket routing
   - Could remove this and let Redis handle it

## Recommendation

**Use Redis Pub/Sub for bidirectional communication:**

1. ✅ Already implemented for edge → consumer
2. ✅ Lower latency than WebSocket routing
3. ✅ Simpler code (no WebSocket bidirectional handling)
4. ✅ Naturally decoupled (consumers don't need ingestion server for predictions)

**Next Steps:**

1. **Update your edge relay code** to subscribe to `user:{user_id}:predictions`
2. **Create a prediction script** for your colleague (like subscribe_to_stream.py but with publish)
3. **Optional:** Remove WebSocket bidirectional code from ingestion server (not needed!)

## FAQ

**Q: Do I need the ingestion server for predictions?**
A: No! With Redis pub/sub, consumers can publish directly to `user:jamie:predictions` and your edge relay can subscribe directly. The ingestion server only needs to forward your raw EEG to Redis.

**Q: Can multiple consumers send predictions?**
A: Yes! All publish to the same channel, your edge relay receives all of them.

**Q: What if Redis goes down?**
A: Messages are lost (pub/sub is not persistent). Use Redis Streams if you need persistence.

**Q: How do I authenticate consumers?**
A: Use Redis ACLs to restrict which consumers can publish/subscribe to which channels.

**Q: Should I use WebSockets or Redis?**
A: Redis pub/sub is simpler and faster for your use case. WebSockets are useful if you need the ingestion server to validate/transform messages before forwarding.
