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

#### `/stream` - Edge Relay Endpoint

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

#### `/subscribe/{user_id}` - Consumer Endpoint

**Subscribe to features/raw EEG** (messages forwarded automatically)

**Send prediction back to edge:**
```json
{
    "type": "prediction",
    "prediction_type": "workload_azure_lstm",
    "classifier_name": "azure_ml_lstm_v2",
    "version": "v2.1.0",
    "data": {
        "workload_prediction": 0.72,
        "confidence": 0.94
    }
}
```

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
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ingestion
REDIS_URL=redis://localhost:6379
EDGE_API_KEY=your-secret-key-here
LOG_LEVEL=INFO
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black app/
ruff check --fix app/
```

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
