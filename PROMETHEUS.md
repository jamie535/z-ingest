# Prometheus Monitoring

The Zander Ingestion Server includes built-in Prometheus metrics for production monitoring.

## Metrics Endpoints

- **`/metrics`** - Standard Prometheus metrics (HTTP requests, latency, etc.)
- **`/metrics-custom`** - Custom application metrics (connections, messages, buffers)

## Available Metrics

### Connection Metrics
- `edge_relay_connections` - Number of active edge relay connections
- `consumer_connections` - Number of active consumer connections

### Message Throughput
- `messages_received_total{message_type, user_id}` - Total messages received
- `messages_processed_total{message_type}` - Successfully processed messages
- `messages_failed_total{message_type, error_type}` - Failed message processing

### Buffer Metrics
- `buffer_size{user_id}` - Current number of samples in buffer
- `buffer_capacity{user_id}` - Maximum buffer capacity

### Session Metrics
- `active_sessions` - Current active sessions
- `sessions_created_total` - Total sessions created
- `sessions_ended_total` - Total sessions ended

### Database Metrics
- `db_writes_total{table}` - Total database writes
- `db_write_duration_seconds{table}` - Database write latency
- `db_batch_size{table}` - Batch size distribution
- `pending_writes{table}` - Records pending write

### HTTP Metrics (from instrumentator)
- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request latency
- `http_requests_in_progress` - Current requests

## Setup with Docker Compose

Add Prometheus and Grafana to your `docker-compose.yml`:

```yaml
version: '3.8'

services:
  ingestion:
    # ... existing config ...
    ports:
      - "8000:8000"

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
    depends_on:
      - prometheus

volumes:
  postgres_data:
  prometheus_data:
  grafana_data:
```

## Prometheus Configuration

Create `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'zander-ingestion'
    static_configs:
      - targets: ['ingestion:8000']
    metrics_path: '/metrics'
```

## Grafana Dashboard

1. Open Grafana: http://localhost:3000 (admin/admin)
2. Add Prometheus data source: http://prometheus:9090
3. Import dashboard or create custom:

### Example Queries

**Message throughput:**
```promql
rate(messages_processed_total[5m])
```

**Buffer usage:**
```promql
buffer_size / buffer_capacity * 100
```

**Connection count:**
```promql
edge_relay_connections + consumer_connections
```

**Error rate:**
```promql
rate(messages_failed_total[5m]) / rate(messages_received_total[5m])
```

**Database write performance:**
```promql
histogram_quantile(0.95, rate(db_write_duration_seconds_bucket[5m]))
```

## Alerts

Example alert rules (`alerts.yml`):

```yaml
groups:
  - name: ingestion_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(messages_failed_total[5m]) > 0.01
        for: 5m
        annotations:
          summary: "High error rate detected"

      - alert: BufferFull
        expr: buffer_size / buffer_capacity > 0.95
        for: 2m
        annotations:
          summary: "Buffer nearly full for {{ $labels.user_id }}"

      - alert: NoConnections
        expr: edge_relay_connections == 0
        for: 10m
        annotations:
          summary: "No edge relays connected"
```

## Production Deployment

For Railway/Fly.io deployment, Prometheus can be added as a separate service or use managed solutions:

- **Grafana Cloud** (free tier available)
- **Datadog** (APM + metrics)
- **New Relic** (full observability)

Add this to your deployment:

```bash
# Environment variable for Grafana Cloud
export PROMETHEUS_REMOTE_WRITE_URL=https://prometheus-us-central1.grafana.net/api/prom/push
export PROMETHEUS_REMOTE_WRITE_USERNAME=your_username
export PROMETHEUS_REMOTE_WRITE_PASSWORD=your_api_key
```
