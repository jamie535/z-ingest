"""Prometheus metrics for ingestion server monitoring."""

from prometheus_client import Counter, Gauge, Histogram, Info

# Application info
app_info = Info("zander_ingestion", "Zander Ingestion Server Information")

# WebSocket connections
edge_connections = Gauge(
    "edge_relay_connections",
    "Number of active edge relay connections"
)

consumer_connections = Gauge(
    "consumer_connections",
    "Number of active consumer connections"
)

# Message throughput
messages_received = Counter(
    "messages_received_total",
    "Total number of messages received",
    ["message_type", "user_id"]
)

messages_processed = Counter(
    "messages_processed_total",
    "Total number of messages successfully processed",
    ["message_type"]
)

messages_failed = Counter(
    "messages_failed_total",
    "Total number of messages that failed processing",
    ["message_type", "error_type"]
)

# Buffer metrics
buffer_size = Gauge(
    "buffer_size",
    "Number of samples in buffer",
    ["user_id"]
)

buffer_capacity = Gauge(
    "buffer_capacity",
    "Maximum buffer capacity",
    ["user_id"]
)

# Database persistence
db_writes_total = Counter(
    "db_writes_total",
    "Total number of database writes",
    ["table"]
)

db_write_duration = Histogram(
    "db_write_duration_seconds",
    "Duration of database write operations",
    ["table"]
)

db_batch_size = Histogram(
    "db_batch_size",
    "Size of database write batches",
    ["table"]
)

pending_writes = Gauge(
    "pending_writes",
    "Number of records pending database write",
    ["table"]
)

# Data quality
sample_latency = Histogram(
    "sample_latency_seconds",
    "Latency from edge relay timestamp to server receipt",
    ["sample_type"]
)

# Session metrics
active_sessions = Gauge(
    "active_sessions",
    "Number of active sessions"
)

sessions_created = Counter(
    "sessions_created_total",
    "Total number of sessions created"
)

sessions_ended = Counter(
    "sessions_ended_total",
    "Total number of sessions ended"
)
