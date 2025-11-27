# Bidirectional Communication Architecture

## Overview

The ingestion server supports bidirectional WebSocket communication with both edge relays and consumers. This document explains the current implementation, design considerations, and recommendations.

## Edge Relay Communication (Bidirectional)

### Current Implementation: WebSocket `/stream`

**Edge relay can SEND:**
- Features data (workload, band powers, metrics)
- Raw EEG samples (channel data)
- Heartbeats

**Edge relay can RECEIVE:**
- Predictions from Azure ML
- Commands (e.g., update sampling rate)
- Alerts (e.g., high cognitive load warnings)
- Auth acknowledgments

### Message Flow (Edge → Server)

```
Edge Relay → WebSocket /stream → Ingestion Server
  ↓
1. Validate message type (features, raw, heartbeat)
2. Add to in-memory buffer
3. Publish to Redis (broadcast to consumers)
4. Queue for database persistence (batched)
```

### Message Flow (Server → Edge)

```
Consumer/Azure ML → Ingestion Server → Edge Relay WebSocket
  ↓
Forward prediction/command/alert to connected edge relay
```

### Design Considerations for Edge Relays

✅ **Current approach is good because:**
- Single persistent WebSocket connection (efficient for streaming)
- Low latency (real-time data)
- Natural fit for continuous EEG streams
- Authentication at connection time

⚠️ **Potential improvements:**
- Add message validation (schema validation with Pydantic)
- Add rate limiting (prevent edge relay from overwhelming server)
- Add compression (reduce bandwidth for raw EEG)
- Add reconnection logic (handle network interruptions)

**Recommendation:** Keep current WebSocket approach for edge relays. It's the right pattern for continuous streaming data.

---

## Consumer Communication (Bidirectional)

### Current Implementation: WebSocket `/subscribe/{user_id}`

**Consumer can RECEIVE:**
- Features data (forwarded from Redis)
- Raw EEG samples (forwarded from Redis)

**Consumer can SEND (current code):**
- Predictions (only type: "prediction" is handled)
- **Problem:** Code is too restrictive, only handles one message type

### Three Patterns for Consumer → Edge Communication

#### Pattern 1: WebSocket Bidirectional (Current)

```python
# Consumer maintains WebSocket connection
async with websockets.connect(f"wss://server.com/subscribe/{user_id}") as ws:
    # Receive data
    data = await ws.recv()

    # Send prediction back
    await ws.send(msgpack.packb({
        "type": "prediction",
        "data": {...}
    }))
```

**Good for:** Real-time services, live dashboards
**Bad for:** Serverless/batch processing (requires persistent connection)

#### Pattern 2: REST API (Not Implemented)

```python
# Consumer gets data via WebSocket (read-only)
# Sends predictions via REST API

import requests

# After processing...
requests.post(f"https://server.com/predictions/{user_id}", json={
    "prediction_type": "workload",
    "data": {...}
})
```

**Good for:** Serverless functions (Azure Functions), batch processing
**Bad for:** Requires two connections (WebSocket + HTTP)

#### Pattern 3: Direct Redis Publish (Not Implemented)

```python
# Consumer subscribes to Redis directly
# Publishes predictions to Redis channel

import redis
r = redis.Redis(...)

# Subscribe to data
pubsub = r.pubsub()
pubsub.subscribe(f"user:{user_id}:features")

# Publish prediction back
r.publish(f"user:{user_id}:predictions", msgpack.packb({...}))

# Ingestion server subscribes to user:*:predictions and forwards to edge relay
```

**Good for:** Fully decoupled microservices, distributed systems
**Bad for:** Requires Redis access for consumers

---

## Recommendations

### For Edge Relays
✅ **Keep WebSocket** - It's the right pattern for continuous streaming

**Improvements to consider:**
1. Add Pydantic schemas for message validation
2. Add rate limiting (max messages/sec)
3. Add compression for raw EEG data
4. Add reconnection handling with exponential backoff

### For Consumers
🔄 **Support Multiple Patterns** - Different Azure ML architectures need different approaches

#### Recommended Implementation:

**1. Fix WebSocket bidirectional (Pattern 1)**
- Make it flexible: handle any message type (prediction, command, alert)
- Make sending back optional (some consumers just read)
- Add proper validation

**2. Add REST endpoint (Pattern 2)**
```python
POST /predictions/{user_id}
Body: {
    "type": "prediction",  # or "command", "alert"
    "data": {...},
    "source": "azure_ml",  # optional
    "timestamp": "2025-11-27T..."  # optional
}
```

**3. Document Redis pattern (Pattern 3)**
- For advanced users who want full decoupling
- Ingestion server subscribes to `user:*:predictions` channel
- Forwards to edge relay WebSocket

---

## Current Issues to Fix

### Consumer WebSocket Endpoint (app/api/websocket.py:148-167)

**Problem 1: Too restrictive**
```python
if msg.get("type") == "prediction":  # Only handles "prediction"
    # What about commands? alerts?
```

**Problem 2: Missing validation**
```python
msg = await websocket.receive_json()  # No schema validation
```

**Problem 3: Session ID confusion**
```python
session_id=msg.get("session_id")  # Consumer might not know session_id
```

**Problem 4: Format mismatch with README**
- README shows format with `timestamp`, `source`, nested `data`
- Code expects flat structure

### Proposed Fix

```python
async def receive_from_consumer():
    while True:
        msg = await websocket.receive_json()

        msg_type = msg.get("type")

        if msg_type in ["prediction", "command", "alert"]:
            # Forward to edge relay
            success = await app.state.connections.send_to_edge(user_id, msg)

            # Store predictions to database
            if success and msg_type == "prediction":
                await store_prediction(app, user_id, msg)
        else:
            logger.warning(f"Unknown message type from consumer: {msg_type}")
```

---

## Security Considerations

### Edge Relays
- ✅ API key authentication (implemented)
- ⚠️ Consider adding rate limiting
- ⚠️ Consider adding user quotas

### Consumers
- ❌ No authentication currently (anyone can connect to `/subscribe/{user_id}`)
- ❌ No authorization (any consumer can send to any user)

**Recommendation:** Add authentication for consumer endpoint:
```python
@router.websocket("/subscribe/{user_id}")
async def consumer_endpoint(
    websocket: WebSocket,
    user_id: str,
    api_key: str = Header(...)  # Require API key
):
    # Validate API key
    # Check if API key has permission for this user_id
```

---

## Summary

| Component | Current | Recommendation |
|-----------|---------|----------------|
| Edge Relay (send) | WebSocket ✅ | Keep, add validation |
| Edge Relay (receive) | WebSocket ✅ | Keep, works well |
| Consumer (receive) | WebSocket ✅ | Keep, works well |
| Consumer (send) | WebSocket (limited) | Fix + add REST endpoint |
| Security | Edge: API key<br>Consumer: None | Add consumer auth |
| Validation | None | Add Pydantic schemas |
| Rate limiting | None | Add for edge relays |

## Next Steps

1. **High Priority:**
   - Fix consumer WebSocket to handle all message types
   - Add REST endpoint `POST /predictions/{user_id}`
   - Add consumer authentication

2. **Medium Priority:**
   - Add Pydantic schemas for message validation
   - Document Redis publish pattern
   - Add rate limiting for edge relays

3. **Low Priority:**
   - Add compression for raw EEG
   - Add reconnection handling
   - Add user quotas
