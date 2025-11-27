# Zander Ingestion Server - Complete Dashboard Setup

Complete dashboard configuration for monitoring your ingestion server in Grafana.

## Create New Dashboard

1. In Grafana, click **+ (Create)** → **Dashboard**
2. Click **Add visualization**
3. Select **Prometheus** as data source

---

## Panel 1: Active Connections (Stat)

**Title**: Active Connections
**Visualization**: Stat
**Query**:
```promql
sum(edge_relay_connections or vector(0)) + sum(consumer_connections or vector(0))
```

**Panel Options**:
- Color scheme: Green/Yellow/Red thresholds
- Thresholds:
  - 0 (red)
  - 1 (yellow)
  - 5 (green)

---

## Panel 2: Edge Relay Connections (Time series)

**Title**: Edge Relay Connections
**Visualization**: Time series
**Query**:
```promql
edge_relay_connections
```

**Panel Options**:
- Legend: `{{instance}}`
- Draw style: Line
- Fill opacity: 10

---

## Panel 3: Consumer Connections (Time series)

**Title**: Consumer Connections
**Visualization**: Time series
**Query**:
```promql
consumer_connections
```

**Panel Options**:
- Legend: `{{instance}}`
- Draw style: Line
- Fill opacity: 10

---

## Panel 4: Active Sessions (Stat)

**Title**: Active Sessions
**Visualization**: Stat
**Query**:
```promql
active_sessions
```

**Panel Options**:
- Color scheme: Single color
- Show: Current value

---

## Panel 5: Session Activity (Time series)

**Title**: Session Activity
**Visualization**: Time series

**Query A** (Sessions Created):
```promql
rate(sessions_created_total[5m])
```
Legend: Sessions Created

**Query B** (Sessions Ended):
```promql
rate(sessions_ended_total[5m])
```
Legend: Sessions Ended

---

## Panel 6: Message Processing Rate (Time series)

**Title**: Messages Per Second
**Visualization**: Time series

**Query A** (Processed):
```promql
rate(messages_processed_total[5m])
```
Legend: `{{message_type}} processed`

**Query B** (Received):
```promql
rate(messages_received_total[5m])
```
Legend: `{{message_type}} received`

---

## Panel 7: Message Totals (Stat)

**Title**: Total Messages Processed
**Visualization**: Stat
**Query**:
```promql
sum(messages_processed_total)
```

**Panel Options**:
- Show: Current value
- Color: Green

---

## Panel 8: Error Rate (Time series)

**Title**: Message Failure Rate
**Visualization**: Time series
**Query**:
```promql
rate(messages_failed_total[5m])
```

**Panel Options**:
- Legend: `{{message_type}} - {{error_type}}`
- Color: Red
- Alert threshold: > 0.01

---

## Panel 9: Error Percentage (Gauge)

**Title**: Error Rate (%)
**Visualization**: Gauge
**Query**:
```promql
(sum(rate(messages_failed_total[5m])) / sum(rate(messages_received_total[5m]))) * 100
```

**Panel Options**:
- Min: 0
- Max: 10
- Thresholds:
  - 0% (green)
  - 1% (yellow)
  - 5% (red)
- Unit: Percent (0-100)

---

## Panel 10: Buffer Usage by User (Bar gauge)

**Title**: Buffer Usage by User
**Visualization**: Bar gauge
**Query**:
```promql
buffer_size
```

**Panel Options**:
- Legend: `{{user_id}}`
- Orientation: Horizontal
- Display mode: Gradient
- Show unfilled: true

---

## Panel 11: Buffer Capacity (Table)

**Title**: Buffer Capacity & Usage
**Visualization**: Table

**Query A** (Size):
```promql
buffer_size
```

**Query B** (Capacity):
```promql
buffer_capacity
```

**Transform**:
- Add field from calculation
- Expression: `$A / $B * 100`
- Alias: Usage %

**Panel Options**:
- Show header: true
- Columns: user_id, buffer_size, buffer_capacity, Usage %

---

## Panel 12: Buffer Utilization (%) (Time series)

**Title**: Buffer Utilization %
**Visualization**: Time series
**Query**:
```promql
(buffer_size / buffer_capacity) * 100
```

**Panel Options**:
- Legend: `User {{user_id}}`
- Unit: Percent (0-100)
- Thresholds:
  - 80% (yellow line)
  - 95% (red line)

---

## Panel 13: Database Writes (Time series)

**Title**: Database Write Rate
**Visualization**: Time series
**Query**:
```promql
rate(db_writes_total[5m])
```

**Panel Options**:
- Legend: `{{table}}`
- Stack: Normal

---

## Panel 14: Database Write Latency (Time series)

**Title**: Database Write Latency (p95)
**Visualization**: Time series
**Query**:
```promql
histogram_quantile(0.95, rate(db_write_duration_seconds_bucket[5m]))
```

**Panel Options**:
- Legend: `{{table}} (p95)`
- Unit: seconds (s)
- Y-axis: Log scale (if high variance)

---

## Panel 15: Database Batch Size (Time series)

**Title**: Database Batch Size
**Visualization**: Time series
**Query**:
```promql
histogram_quantile(0.50, rate(db_batch_size_bucket[5m]))
```

**Panel Options**:
- Legend: `{{table}} (median)`

---

## Panel 16: Pending Database Writes (Gauge)

**Title**: Pending Database Writes
**Visualization**: Gauge
**Query**:
```promql
sum(pending_writes) by (table)
```

**Panel Options**:
- Legend: `{{table}}`
- Thresholds:
  - 0 (green)
  - 100 (yellow)
  - 1000 (red)

---

## Panel 17: Sample Latency (Time series)

**Title**: Sample Latency (Edge to Server)
**Visualization**: Time series
**Query**:
```promql
histogram_quantile(0.95, rate(sample_latency_seconds_bucket[5m]))
```

**Panel Options**:
- Legend: `{{sample_type}} (p95)`
- Unit: seconds (s)

---

## Panel 18: HTTP Request Rate (Time series)

**Title**: HTTP Requests/sec
**Visualization**: Time series
**Query**:
```promql
rate(http_requests_total[5m])
```

**Panel Options**:
- Legend: `{{method}} {{handler}}`

---

## Panel 19: HTTP Request Duration (Time series)

**Title**: HTTP Request Duration (p95)
**Visualization**: Time series
**Query**:
```promql
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

**Panel Options**:
- Legend: `{{handler}} (p95)`
- Unit: seconds (s)

---

## Panel 20: System Metrics - Python GC (Time series)

**Title**: Python Garbage Collection
**Visualization**: Time series

**Query A**:
```promql
rate(python_gc_collections_total[5m])
```
Legend: `Gen {{generation}}`

---

## Panel 21: Application Info (Stat)

**Title**: Application Info
**Visualization**: Stat
**Query**:
```promql
zander_ingestion_info
```

**Panel Options**:
- Show: Labels as fields

---

## Dashboard Layout Suggestion

**Row 1 - Overview** (Full width):
- Panel 1: Active Connections (Stat, 1/4 width)
- Panel 4: Active Sessions (Stat, 1/4 width)
- Panel 7: Total Messages (Stat, 1/4 width)
- Panel 9: Error Rate % (Gauge, 1/4 width)

**Row 2 - Connections** (Full width):
- Panel 2: Edge Relay Connections (Time series, 1/2 width)
- Panel 3: Consumer Connections (Time series, 1/2 width)

**Row 3 - Sessions** (Full width):
- Panel 5: Session Activity (Time series, full width)

**Row 4 - Messages** (Full width):
- Panel 6: Message Processing Rate (Time series, 3/4 width)
- Panel 8: Error Rate (Time series, 1/4 width)

**Row 5 - Buffer** (Full width):
- Panel 12: Buffer Utilization % (Time series, 1/2 width)
- Panel 10: Buffer Usage by User (Bar gauge, 1/2 width)

**Row 6 - Buffer Details** (Full width):
- Panel 11: Buffer Capacity Table (Table, full width)

**Row 7 - Database** (Full width):
- Panel 13: Database Write Rate (Time series, 1/3 width)
- Panel 14: DB Write Latency (Time series, 1/3 width)
- Panel 16: Pending Writes (Gauge, 1/3 width)

**Row 8 - Database Details** (Full width):
- Panel 15: Batch Size (Time series, 1/2 width)
- Panel 17: Sample Latency (Time series, 1/2 width)

**Row 9 - HTTP** (Full width):
- Panel 18: HTTP Request Rate (Time series, 1/2 width)
- Panel 19: HTTP Duration (Time series, 1/2 width)

**Row 10 - System** (Full width):
- Panel 20: Python GC (Time series, full width)

---

## Dashboard Variables (Optional)

Add variables for filtering:

**Variable 1 - User ID**:
- Name: `user_id`
- Type: Query
- Query: `label_values(buffer_size, user_id)`
- Multi-value: true
- Include All option: true

Then use `{{user_id}}` in queries:
```promql
buffer_size{user_id=~"$user_id"}
```

**Variable 2 - Time Range**:
- Name: `interval`
- Type: Interval
- Values: `1m,5m,10m,30m,1h`
- Auto: true

Use in queries:
```promql
rate(messages_processed_total[$interval])
```

---

## Save Dashboard

1. Click **Save dashboard** (disk icon, top right)
2. Name: "Zander Ingestion Server"
3. Add tags: `ingestion`, `production`, `eeg`
4. Click **Save**

---

## Set Up Alerts

After creating the dashboard, add alerts:

### Alert 1: High Error Rate
- Panel: Error Rate %
- Condition: `WHEN avg() OF query(A, 5m, now) IS ABOVE 5`
- Evaluate every: 1m
- For: 5m

### Alert 2: Buffer Nearly Full
- Panel: Buffer Utilization %
- Condition: `WHEN max() OF query(A, 5m, now) IS ABOVE 95`
- Evaluate every: 30s
- For: 2m

### Alert 3: No Connections
- Panel: Active Connections
- Condition: `WHEN last() OF query(A, 5m, now) IS BELOW 1`
- Evaluate every: 1m
- For: 10m

### Alert 4: High DB Latency
- Panel: DB Write Latency
- Condition: `WHEN avg() OF query(A, 5m, now) IS ABOVE 1`
- Evaluate every: 1m
- For: 5m

---

## Quick Import Alternative

If you want to import these quickly, you can also:

1. **Import FastAPI Dashboard first**:
   - ID: `16110`
   - This gives you HTTP metrics automatically

2. **Then create custom dashboard** with the buffer, session, and message metrics above

---

## Tips

- Use **template variables** for filtering by user_id
- Set **auto-refresh** to 30s for real-time monitoring
- Add **annotations** for deployments
- Use **dashboard links** to navigate between dashboards
- Set up **notification channels** for alerts (Slack, email, etc.)
