# Grafana Cloud Monitoring Setup

Simple guide to monitor your Railway ingestion service with Grafana Cloud.

## Using Railway's Grafana Alloy Template

Railway has a pre-built template that handles everything for you.

### Step 1: Deploy the Template

1. Go to: https://railway.com/deploy/railway-grafana-allo
2. Click **Deploy Now**
3. Select your Railway project (same one as your ingestion service)
4. Railway creates a new `grafana-alloy` service

### Step 2: Configure Grafana Cloud Credentials

In the new `grafana-alloy` service:

1. Go to **Variables** tab
2. Add these 3 variables (get from Grafana Cloud → Connections → Hosted Prometheus):

```
GRAFANA_CLOUD_URL=<your-prometheus-push-url>
GRAFANA_CLOUD_USERNAME=<your-instance-id>
GRAFANA_CLOUD_API_KEY=<your-api-key>
```

Example:
- URL: `https://prometheus-prod-65-prod-eu-west-2.grafana.net/api/prom/push`
- Username: `2827197`
- API Key: `glc_...` (from Grafana Cloud)

### Step 3: Configure Alloy to Scrape Your App

The template exposes HTTP endpoints. You need to tell it where to scrape your metrics.

Check the template's documentation for configuration details, or configure via Alloy's config file to scrape:
```
https://jubilant-warmth.railway.internal:8080/metrics
```

### Step 4: Verify in Grafana Cloud

After 2 minutes:

1. Go to **Explore** in Grafana Cloud
2. Select **Prometheus** data source
3. Query: `up{job="zander-ingestion"}`
4. Should see your metrics!

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

- **Grafana Cloud**: Free tier (10k series, 14 days retention)
- **Railway Alloy service**: ~$2-5/month

## Troubleshooting

**No metrics in Grafana Cloud:**
- Check Alloy service logs in Railway
- Verify Grafana Cloud credentials
- Wait 2-3 minutes for initial data

**Connection errors:**
- Ensure your ingestion service exposes `/metrics`
- Check Railway private networking is enabled
- Verify service name: `jubilant-warmth.railway.internal`

## Links

- Railway Alloy Template: https://railway.com/deploy/railway-grafana-allo
- Grafana Cloud: https://grafana.com
- Your ingestion service metrics: https://jubilant-warmth-production.up.railway.app/metrics
