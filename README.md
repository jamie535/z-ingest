# Zander Ingestion Server

Lightweight bidirectional WebSocket broker for EEG data streams. Receives features and raw EEG from edge relays, broadcasts to multiple consumers (MCP server, Azure ML, analytics apps).

## Project Structure

```
zander-ingestion-server/
├── app/
│   ├── main.py                 # FastAPI app + lifespan
│   ├── config.py               # Settings (Pydantic)
│   ├── api/                    # API endpoints
│   │   ├── websocket.py       # WebSocket endpoints
│   │   └── rest.py            # REST endpoints (health, buffer)
│   ├── core/                   # Core business logic
│   │   ├── buffer.py          # StreamBuffer
│   │   ├── connections.py     # ConnectionManager
│   │   └── handlers.py        # Message handlers
│   └── db/                     # Database layer
│       ├── models.py          # SQLAlchemy models
│       ├── database.py        # DatabaseManager
│       └── persistence.py     # PersistenceManager
├── tests/
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## Architecture

```
Edge Relays (EEG devices)
    ↓ WebSocket /stream
┌──────────────────────────────────────────┐
│  Ingestion Server (FastAPI + Redis)     │
├──────────────────────────────────────────┤
│  - ConnectionManager (WebSocket registry)│
│  - StreamBuffer (in-memory queries)      │
│  - PersistenceManager (batched DB)       │
│  - Redis pub/sub (broadcast)             │
└──────────────────────────────────────────┘
    ↓ Redis channels
Consumers (MCP, Azure ML, Analytics)
    ↓ WebSocket /subscribe/{user_id}
```

## Features

- ✅ **Bidirectional WebSocket** - Edge relays push features, receive predictions from Azure
- ✅ **Redis pub/sub** - Broadcast to multiple consumers in real-time
- ✅ **In-memory buffer** - Query last N samples, time ranges
- ✅ **TimescaleDB persistence** - Batched writes (50 records or 5s)
- ✅ **Extensible schema** - Support multiple prediction types from different Azure models
- ✅ **Raw EEG support** - Full signal data for Azure ML models and visualization

## Quick Start

### 1. Install Dependencies

```bash
pip install -e .
```

### 2. Start Services

```bash
# Start PostgreSQL + Redis
docker-compose up -d

# Set environment variables
cp .env.example .env
# Edit .env with your DATABASE_URL, REDIS_URL, EDGE_API_KEY
```

### 3. Run Server

```bash
python -m app.main
```

Server runs on `http://localhost:8000`
- WebSocket (edge relays): `ws://localhost:8000/stream`
- WebSocket (consumers): `ws://localhost:8000/subscribe/{user_id}`
- Health check: `http://localhost:8000/health`
- API docs: `http://localhost:8000/docs`

## API Endpoints

### WebSocket Endpoints

#### `/stream` - Edge Relay Endpoint (Bidirectional)

Edge relays can both **send** data (features, raw EEG) and **receive** data (predictions, commands, alerts) over the same WebSocket connection.

**Authentication (first message):**
```json
{
    "type": "auth",
    "api_key": "your-api-key",
    "user_id": "user_123",
    "device_info": {
        "device_type": "Emotiv EPOC",
        "sampling_rate": 128,
        "channel_names": ["F3", "F4", "C3", "Cz", "C4", "P3", "P4"],
        "channel_count": 7
    }
}
```

**Send features:**
```json
{
    "type": "features",
    "workload": 0.65,
    "confidence": 0.89,
    "band_powers": {"delta": 0.12, "theta": 0.25, "alpha": 0.35, ...},
    "metrics": {"frontal_theta": 0.22, "theta_beta_ratio": 1.38, ...}
}
```

**Send raw EEG:**
```json
{
    "type": "raw",
    "channels": [0.1, 0.2, -0.3, 0.15, 0.22, -0.1, 0.3]
}
```

**Receive predictions from Azure ML:**
```json
{
    "type": "prediction",
    "timestamp": "2025-11-27T16:00:00Z",
    "source": "azure_ml",
    "data": {
        "model_name": "workload_lstm_v2",
        "workload_prediction": 0.78,
        "confidence": 0.92,
        "next_5min_trend": "increasing"
    }
}
```

**Receive commands:**
```json
{
    "type": "command",
    "command": "update_sampling_rate",
    "parameters": {
        "sampling_rate": 256
    }
}
```

**Receive alerts:**
```json
{
    "type": "alert",
    "alert_type": "high_workload",
    "severity": "warning",
    "message": "Cognitive load exceeding 80% for 5 minutes",
    "metadata": {
        "current_workload": 0.85,
        "duration_seconds": 300
    }
}
```

#### `/subscribe/{user_id}` - Consumer Endpoint (Bidirectional)

**Receive features/raw EEG** (messages forwarded automatically via Redis pub/sub)

**Send prediction back to edge relay:**

Consumers (like Azure ML services) can send predictions back to the edge relay through the ingestion server:

```python
# In your Azure ML consumer/service
import websockets
import msgpack

async with websockets.connect("wss://your-server.com/subscribe/user_123") as ws:
    # Receive data from edge relay
    data = await ws.recv()
    features = msgpack.unpackb(data)

    # Process with Azure ML
    prediction = await azure_ml_model.predict(features)

    # Send prediction back to edge relay
    response = {
        "type": "prediction",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "azure_ml",
        "data": {
            "model_name": "workload_lstm_v2",
            "workload_prediction": prediction["workload"],
            "confidence": prediction["confidence"]
        }
    }
    await ws.send(msgpack.packb(response))
```

The ingestion server will automatically forward this prediction to the connected edge relay.

### REST Endpoints

- `GET /health` - Health check
- `GET /health/ready` - Readiness check (includes DB/Redis)
- `GET /buffer/{user_id}/latest?sample_type=features` - Get latest sample
- `GET /buffer/{user_id}/last/{n}?sample_type=features` - Get last N samples
- `GET /buffer/{user_id}/stats` - Buffer statistics
- `GET /stats` - Server statistics

## Database Schema

### Sessions
```sql
session_id      UUID PRIMARY KEY
user_id         VARCHAR(100) NOT NULL
start_time      TIMESTAMPTZ NOT NULL
end_time        TIMESTAMPTZ
device_info     JSONB  -- {"sampling_rate": 128, "channel_names": [...]}
```

### Predictions (TimescaleDB hypertable)
```sql
timestamp           TIMESTAMPTZ PRIMARY KEY
session_id          UUID NOT NULL
user_id             VARCHAR(100) NOT NULL
prediction_type     VARCHAR(50) NOT NULL  -- "workload_edge", "emotion_azure", etc.
classifier_name     VARCHAR(100) NOT NULL -- "edge_relay", "azure_ml_lstm_v2", etc.
data                JSONB NOT NULL        -- Flexible prediction data
confidence          FLOAT
classifier_version  VARCHAR(50)
```

### Raw Samples (TimescaleDB hypertable)
```sql
timestamp       TIMESTAMPTZ PRIMARY KEY
session_id      UUID NOT NULL
user_id         VARCHAR(100) NOT NULL
data            JSONB NOT NULL  -- {"channels": [0.1, 0.2, ...]}
```

## Configuration

Edit `.env`:

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ingestion

# Redis
REDIS_URL=redis://localhost:6379

# Authentication
EDGE_API_KEY=your-secret-key-here

# Server
LOG_LEVEL=INFO

# Persistence Configuration (Optional)
# Set to false to disable database/redis persistence during development
# Data will only be kept in memory (lost on restart)
ENABLE_DB_PERSISTENCE=true
ENABLE_REDIS_PUBSUB=true
```

## Development

```bash
# Install with dev dependencies
pip install -e .

# Run tests
pytest

# Run Redis pub/sub tests
pytest tests/test_redis_pubsub.py -v

# Subscribe to live streams (for testing)
python scripts/subscribe_to_stream.py user123 both

# Format code
ruff check --fix app/
```

## Testing

See [tests/README.md](tests/README.md) for comprehensive testing guide including:
- Redis pub/sub tests
- Live stream subscriber
- Integration testing
- Performance testing

## Deployment

### Railway / Fly.io

```bash
# Set environment variables
railway run set DATABASE_URL=...
railway run set REDIS_URL=...
railway run set EDGE_API_KEY=...

# Deploy
railway up
```

### Docker

```bash
docker build -t zander-ingestion-server .
docker run -p 8000:8000 \
  -e DATABASE_URL=... \
  -e REDIS_URL=... \
  -e EDGE_API_KEY=... \
  zander-ingestion-server
```

## Performance

- **Latency:** <100ms edge → consumer
- **Throughput:** Handles 100 concurrent edge relays
- **Database writes:** Batched (50 records or 5s) for efficiency
- **Memory:** ~1000 samples buffered per user (~100 KB per user)

## License

MIT
