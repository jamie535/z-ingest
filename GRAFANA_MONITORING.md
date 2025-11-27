# Grafana Monitoring Setup

Complete self-hosted monitoring stack on Railway for your ingestion service.

## Using Railway's Grafana Stack Template

Railway has a complete observability stack template (Grafana + Prometheus + Loki + Tempo).

### Step 1: Deploy the Template

1. Go to: https://railway.app/template/8TLSQD
2. Click **Deploy Now**
3. Select your Railway project (same one as your ingestion service)
4. Railway creates: Grafana, Prometheus, Loki, and Tempo services

### Step 2: Fork and Configure Prometheus

To add your ingestion service as a scrape target:

1. **Fork the template repo**: https://github.com/MykalMachon/railway-grafana-stack
2. **Edit** `prometheus/prometheus.yml` in your fork
3. **Add** your scrape job:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'zander-ingestion'
    scheme: http
    static_configs:
      - targets: ['jubilant-warmth.railway.internal:8080']
    metrics_path: '/metrics'
```

4. **Commit** the changes to your fork

### Step 3: Update Railway Prometheus Service

1. In Railway → **Prometheus service** → **Settings** → **Source**
2. Click **Disconnect**
3. **Connect to GitHub Repo** → Select your forked repo
4. Set **Root Directory**: `prometheus`
5. Railway redeploys Prometheus with your config

### Step 4: Verify in Grafana

After 2 minutes:

1. Open your Grafana URL (from Railway service)
2. Login (check `GF_SECURITY_ADMIN_USER` and `GF_SECURITY_ADMIN_PASSWORD` variables)
3. Go to **Explore** → Select **Prometheus**
4. Query: `up{job="zander-ingestion"}`
5. Should return `1` - success! ✅

Then try your custom metrics:
```promql
edge_relay_connections + consumer_connections
```

## Create Dashboards

### Import FastAPI Dashboard

1. Dashboards → Import
2. Dashboard ID: **16110**
3. Select Prometheus data source

### Custom Queries

**Active Connections:**
```promql
edge_relay_connections + consumer_connections
```

**Message Processing Rate:**
```promql
rate(messages_processed_total[5m])
```

**Error Rate (%):**
```promql
rate(messages_failed_total[5m]) / rate(messages_received_total[5m]) * 100
```

**Buffer Usage (%):**
```promql
(buffer_size / buffer_capacity) * 100
```

**Database Write Latency (p95):**
```promql
histogram_quantile(0.95, rate(db_write_duration_seconds_bucket[5m]))
```

**Active Sessions:**
```promql
active_sessions
```

## Set Up Alerts

1. Go to **Alerting** → **Alert rules** → **New alert rule**
2. Example alerts:

**High Error Rate:**
```promql
rate(messages_failed_total[5m]) / rate(messages_received_total[5m]) > 0.01
```

**Buffer Nearly Full:**
```promql
buffer_size / buffer_capacity > 0.95
```

**No Connections:**
```promql
edge_relay_connections == 0
```

## Cost

- **Grafana Stack on Railway**: ~$10-15/month total for all services
  - Grafana: ~$3-5/month
  - Prometheus: ~$3-5/month
  - Loki: ~$2-3/month
  - Tempo: ~$2-3/month
- **Benefits**: Complete self-hosted observability, no external dependencies

## Troubleshooting

**No metrics showing:**
- Check Prometheus is scraping: Query `up` in Grafana Explore
- Verify your ingestion service exposes `/metrics`: Visit https://jubilant-warmth-production.up.railway.app/metrics
- Check Prometheus logs in Railway for errors

**Target down:**
- Ensure Railway private networking is enabled on ingestion service
- Verify service internal DNS: `jubilant-warmth.railway.internal`
- Check port is correct: `8080`

**YAML parse errors:**
- Check `prometheus.yml` indentation (use spaces, not tabs)
- Validate YAML syntax
- Check Prometheus logs for specific line numbers

## Links

- Railway Grafana Stack Template: https://railway.app/template/8TLSQD
- Template GitHub Repo: https://github.com/MykalMachon/railway-grafana-stack
- Your ingestion service metrics: https://jubilant-warmth-production.up.railway.app/metrics
