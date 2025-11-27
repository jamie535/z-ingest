# Services Explained & Configuration

## Current Services in Railway

### 1. **Ingestion Service** (z-ingest / jubilant-warmth)
**What it does:**
- Receives EEG data from edge devices via WebSocket
- Stores data in 3 places:
  1. **Buffer** (in-memory) - for fast queries
  2. **Redis** (pub/sub) - broadcasts to consumers in real-time
  3. **PostgreSQL/TimescaleDB** (persistent) - long-term storage

**Cost:** ~$5-10/month

### 2. **PostgreSQL/TimescaleDB**
**What it does:**
- Persistent storage for all EEG data
- TimescaleDB extension for time-series optimization
- Stores: raw samples, features, sessions

**Currently:** **Required** - data is always persisted

**Cost:** ~$10-15/month (depends on volume size)

**Problem:** Volume is full (1GB) - needs to be increased to 5-10GB

### 3. **Redis**
**What it does:**
- **Pub/Sub messaging** - broadcasts data to consumer applications in real-time
- When edge device sends data → Redis publishes to channel → Consumers receive instantly

**Currently:** **Required for real-time consumers**

**Cost:** ~$3-5/month

**Is it being used?** Yes - every time data arrives, it's published to Redis channels:
- `user:{user_id}:features`
- `user:{user_id}:raw`

### 4. **Grafana Stack** (Grafana, Prometheus, Loki, Tempo)
**What it does:**
- **Grafana** - Dashboard UI
- **Prometheus** - Metrics storage
- **Loki** - Logs storage
- **Tempo** - Traces storage

**Currently:** Monitoring your ingestion service

**Cost:** ~$10-15/month total

---

## Making Persistence Optional

You want to be able to turn database persistence on/off to save costs during development.

### Add to `app/config.py`:

```python
class Settings(BaseSettings):
    """Application settings."""

    # Database
    database_url: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/ingestion")

    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Authentication
    edge_api_key: str = os.getenv("EDGE_API_KEY", "")

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Buffer
    buffer_max_size: int = 1000

    # Persistence Configuration
    enable_database_persistence: bool = os.getenv("ENABLE_DB_PERSISTENCE", "true").lower() == "true"
    enable_redis_pubsub: bool = os.getenv("ENABLE_REDIS_PUBSUB", "true").lower() == "true"
    batch_size: int = 50
    flush_interval: float = 5.0
```

### Update `app/core/handlers.py`:

```python
from ..config import settings

async def handle_features(app, user_id: str, session_id: UUID, data: dict):
    """Process incoming features from edge relay."""
    timestamp = datetime.now(timezone.utc)

    # Track message received
    metrics.messages_received.labels(message_type="features", user_id=user_id).inc()

    try:
        # 1. Add to buffer (always enabled)
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

        # 2. Publish to Redis (optional)
        if settings.enable_redis_pubsub:
            try:
                await app.state.redis.publish(
                    f"user:{user_id}:features",
                    msgpack.packb(data)
                )
            except Exception as e:
                logger.error(f"Redis publish error: {e}")

        # 3. Queue for database (optional)
        if settings.enable_database_persistence:
            await app.state.persistence.queue_sample(
                user_id=user_id,
                session_id=session_id,
                timestamp=timestamp,
                data=data,
                sample_type="features"
            )

        metrics.messages_processed.labels(message_type="features").inc()

    except Exception as e:
        logger.error(f"Error handling features: {e}")
        metrics.messages_failed.labels(message_type="features", error_type=type(e).__name__).inc()
        raise
```

### Railway Environment Variables:

Add to your ingestion service in Railway:

```bash
# Development mode - no persistence
ENABLE_DB_PERSISTENCE=false
ENABLE_REDIS_PUBSUB=false

# Production mode - full persistence
ENABLE_DB_PERSISTENCE=true
ENABLE_REDIS_PUBSUB=true
```

---

## Cost Optimization Strategies

### Development/Testing:
**Minimal setup** (~$5-10/month):
- ✅ Ingestion service only
- ❌ No PostgreSQL (set `ENABLE_DB_PERSISTENCE=false`)
- ❌ No Redis (set `ENABLE_REDIS_PUBSUB=false`)
- ❌ No Grafana stack (remove services)
- Data is only in memory (lost on restart)

### Production:
**Full stack** (~$30-40/month):
- ✅ Ingestion service
- ✅ PostgreSQL/TimescaleDB (with data retention policies)
- ✅ Redis (for real-time consumers)
- ✅ Grafana stack (monitoring)

### Hybrid:
**Database only** (~$15-20/month):
- ✅ Ingestion service
- ✅ PostgreSQL (persistent storage)
- ❌ No Redis (no real-time broadcast)
- ❌ No Grafana (use Railway metrics)

---

## Fix Current PostgreSQL Issue

**Immediate action needed:**

1. **Increase PostgreSQL volume size:**
   - Railway → PostgreSQL service → Settings → Volumes
   - Increase from 1GB to at least **5GB** (or 10GB for safety)
   - Cost: ~$1-2/month for 5GB

2. **Add data retention policy** (after volume is fixed):

```sql
-- Keep raw samples for 30 days
SELECT add_retention_policy('eeg_samples', INTERVAL '30 days');

-- Keep features for 90 days
SELECT add_retention_policy('eeg_features', INTERVAL '90 days');

-- Keep sessions forever
-- (don't add retention policy)
```

3. **Configure WAL cleanup:**

Add to PostgreSQL service environment variables:
```
POSTGRES_MAX_WAL_SIZE=1GB
POSTGRES_MIN_WAL_SIZE=80MB
```

---

## Summary

| Service | Purpose | Currently Used? | Can Disable? | Cost/Month |
|---------|---------|----------------|--------------|------------|
| Ingestion | Main app | ✅ Yes | ❌ No | $5-10 |
| PostgreSQL | Persistent storage | ✅ Yes | ✅ Yes (dev only) | $10-15 |
| Redis | Real-time pub/sub | ✅ Yes | ✅ Yes (if no consumers) | $3-5 |
| Grafana Stack | Monitoring | ✅ Yes | ✅ Yes (optional) | $10-15 |

**Total:** $28-45/month (full stack)
**Minimum:** $5-10/month (ingestion only, dev mode)

---

## Next Steps

1. **Immediate:** Increase PostgreSQL volume to 5-10GB
2. **Add:** Persistence toggle environment variables
3. **Update:** Code to check settings before persisting
4. **Configure:** Data retention policies in TimescaleDB
5. **Test:** Dev mode with persistence disabled
