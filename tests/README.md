# Testing Guide

## Running Redis Pub/Sub Tests

### Prerequisites

1. **Redis must be running:**
   ```bash
   # Local (via docker-compose)
   docker-compose up redis -d

   # Or check Railway Redis is accessible
   ```

2. **Install test dependencies:**
   ```bash
   pip install pytest pytest-asyncio
   ```

### Run All Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_redis_pubsub.py

# Run specific test
pytest tests/test_redis_pubsub.py::test_subscribe_to_features_stream -v
```

### Test Coverage

The test suite covers:

1. **Basic Connection** - Tests Redis connectivity
2. **Publish Features** - Tests publishing feature data to Redis
3. **Subscribe to Features** - Tests receiving features in real-time
4. **Subscribe to Raw Samples** - Tests receiving raw EEG data
5. **Multiple Subscribers** - Tests that multiple consumers receive the same message
6. **Channel Isolation** - Tests that user channels are isolated
7. **Msgpack Serialization** - Tests complex data structure serialization
8. **Settings Toggle** - Tests that Redis pub/sub can be disabled

## Manual Testing with Real Streams

### Subscribe to Live Edge Relay Stream

Use the included script to subscribe to real-time streams:

```bash
# Subscribe to features only
python scripts/subscribe_to_stream.py user123 features

# Subscribe to raw EEG samples only
python scripts/subscribe_to_stream.py user123 raw

# Subscribe to both streams
python scripts/subscribe_to_stream.py user123 both
```

### What You'll See

**Features stream:**
```
[14:23:45.123] FEATURES:
  Workload: high
  Confidence: 95.00%
  Features:
    alpha: 0.623
    beta: 0.234
    theta: 0.143
```

**Raw EEG stream:**
```
[14:23:45.456] RAW SAMPLE #1234:
  Channels:
    AF7:    0.234 µV
    AF8:   -0.123 µV
    TP9:    0.456 µV
    TP10:  -0.789 µV
  Sample #: 12345
```

## Testing with Edge Relay

### 1. Start the Ingestion Server

```bash
# Local
uvicorn app.main:app --reload

# Or use Railway deployment
```

### 2. Connect an Edge Relay

The edge relay device should connect via WebSocket to:
```
ws://localhost:8000/ws/edge/{user_id}?api_key=your-key
```

### 3. Subscribe to the Stream

In another terminal:
```bash
python scripts/subscribe_to_stream.py {user_id} both
```

### 4. Send Data from Edge Relay

As the edge relay sends data, you'll see it appear in real-time in the subscriber terminal!

## Testing Persistence Toggle

### Disable Persistence

```bash
# In .env or Railway environment variables
ENABLE_DB_PERSISTENCE=false
ENABLE_REDIS_PUBSUB=false
```

Then test that:
1. Data is still buffered (in-memory)
2. No database writes occur
3. No Redis messages are published

### Verify

```python
from app.config import settings

print(f"DB Persistence: {settings.enable_database_persistence}")
print(f"Redis Pub/Sub: {settings.enable_redis_pubsub}")
```

## CI/CD Integration

Add to your CI pipeline:

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio

      - name: Run tests
        env:
          REDIS_URL: redis://localhost:6379
        run: pytest -v
```

## Troubleshooting

### Test Timeout

If tests timeout, Redis might not be running:
```bash
# Check Redis
redis-cli ping
# Should return: PONG

# Or with Docker
docker ps | grep redis
```

### Connection Refused

Update Redis URL in `.env`:
```bash
# Local
REDIS_URL=redis://localhost:6379

# Railway
REDIS_URL=redis://default:password@redis.railway.internal:6379
```

### Msgpack Import Error

```bash
pip install msgpack
```

## Performance Testing

### Test High-Frequency Streaming

```python
# In Python REPL
import asyncio
from redis.asyncio import Redis
import msgpack
from datetime import datetime, timezone

async def stress_test():
    redis = Redis.from_url("redis://localhost:6379")

    # Send 1000 samples/sec
    for i in range(1000):
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sample_number": i,
            "channels": {"AF7": 0.1 * i}
        }
        await redis.publish(
            "user:test:raw",
            msgpack.packb(data)
        )
        await asyncio.sleep(0.001)  # 1ms = 1000 Hz

    await redis.aclose()

asyncio.run(stress_test())
```

Monitor with the subscriber:
```bash
python scripts/subscribe_to_stream.py test raw
```

## Next Steps

1. Add integration tests with full WebSocket flow
2. Add load tests for concurrent subscribers
3. Add tests for error handling and reconnection
4. Add tests for buffer overflow scenarios
