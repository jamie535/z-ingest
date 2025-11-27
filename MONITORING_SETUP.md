# Monitoring Setup Guide - Railway

## Steps to Add Prometheus + Grafana

### 1. Delete the Old Grafana Stack (if present)

In Railway dashboard, delete all services from the Grafana stack template.

### 2. Create Prometheus Service

1. In Railway, click **+ New** → **Empty Service**
2. Name it: `prometheus`
3. Go to **Settings** → **Dockerfile Path**: `Dockerfile.prometheus`
4. Go to **Variables**, add:
   - `ZANDER_INGESTION_URL` = `${{zander-ingestion.RAILWAY_PRIVATE_DOMAIN}}:${{zander-ingestion.PORT}}`
5. **Deploy from GitHub** or upload files:
   - `prometheus.yml`
   - `Dockerfile.prometheus`
6. Add a **Volume**:
   - Mount Path: `/prometheus`
   - This persists metrics data

### 3. Create Grafana Service

1. In Railway, click **+ New** → **Empty Service**
2. Name it: `grafana`
3. Go to **Settings** → **Dockerfile Path**: `Dockerfile.grafana`
4. Go to **Variables**, add:
   - `GF_SECURITY_ADMIN_USER` = `admin`
   - `GF_SECURITY_ADMIN_PASSWORD` = `your-secure-password`
   - `GF_SERVER_ROOT_URL` = `https://${{RAILWAY_PUBLIC_DOMAIN}}`
5. **Deploy from GitHub** or upload `Dockerfile.grafana`
6. Add a **Volume**:
   - Mount Path: `/var/lib/grafana`
   - This persists dashboards and settings
7. **Generate Public Domain** (so you can access Grafana)

### 4. Configure Grafana Data Source

1. Open Grafana: `https://your-grafana.up.railway.app`
2. Login with admin credentials
3. Go to **Connections** → **Data Sources** → **Add data source**
4. Select **Prometheus**
5. Set URL: `http://${{prometheus.RAILWAY_PRIVATE_DOMAIN}}:9090`
   - Or use Railway reference: Create a variable in Grafana service:
     - `PROMETHEUS_URL` = `http://${{prometheus.RAILWAY_PRIVATE_DOMAIN}}:9090`
     - Then in Grafana UI, use: `${PROMETHEUS_URL}`
6. Click **Save & Test**

### 5. Import Dashboard

1. In Grafana, click **+** → **Import Dashboard**
2. Use dashboard ID: `11074` (Prometheus Stats) or create custom
3. Create custom panels with these queries:

**Message Throughput:**
```promql
rate(messages_processed_total[5m])
```

**Active Connections:**
```promql
edge_relay_connections
```

**Buffer Usage:**
```promql
(buffer_size / buffer_capacity) * 100
```

**Error Rate:**
```promql
rate(messages_failed_total[5m]) / rate(messages_received_total[5m])
```

**Database Write Performance:**
```promql
histogram_quantile(0.95, rate(db_write_duration_seconds_bucket[5m]))
```

## Alternative: Quick Setup with Railway CLI

If you prefer CLI:

```bash
# Add Prometheus
railway service create prometheus
railway link prometheus
railway up -d -f Dockerfile.prometheus

# Add Grafana
railway service create grafana
railway link grafana
railway up -d -f Dockerfile.grafana
```

## Troubleshooting

**Prometheus can't scrape ingestion server:**
- Check the `ZANDER_INGESTION_URL` variable is set correctly
- Verify private networking is enabled
- Check Prometheus logs: `railway logs prometheus`

**Grafana can't connect to Prometheus:**
- Verify Prometheus URL uses Railway private domain
- Check both services are in the same project
- Test from Grafana terminal: `curl http://prometheus.railway.internal:9090`

**No data showing:**
- Wait 15-30 seconds for first scrape
- Check Prometheus targets: `http://your-prometheus.up.railway.app/targets`
- Verify ingestion server `/metrics` endpoint is accessible
