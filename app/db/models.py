"""SQLAlchemy models for ingestion server database schema.

Design principles:
- Metadata stored once in Session (no redundancy)
- Denormalized user_id for fast queries
- JSONB for flexible data storage
- TimescaleDB hypertables for time-series optimization
"""

from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    Float,
    BigInteger,
    DateTime,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()  # type: ignore[misc]


class Session(Base):  # type: ignore[misc,valid-type]
    """Recording session - stores metadata once.

    device_info structure:
    {
        "device_type": "Emotiv EPOC",
        "sampling_rate": 128,
        "channel_names": ["F3", "F4", "C3", "Cz", "C4", "P3", "P4"],
        "channel_count": 7
    }
    """

    __tablename__ = "sessions"

    session_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(String(100), nullable=False, index=True)
    start_time = Column(DateTime(timezone=True), nullable=False, default=func.now())
    end_time = Column(DateTime(timezone=True), nullable=True)
    device_info = Column(JSONB, nullable=True)

    def __repr__(self):
        return f"<Session {self.session_id} user={self.user_id}>"


class Prediction(Base):  # type: ignore[misc,valid-type]
    """Predictions from edge relays or Azure ML models.

    TimescaleDB hypertable for time-series optimization.

    Extensible schema via prediction_type + classifier_name + data JSONB:

    Edge relay workload:
    {
        "prediction_type": "workload_edge",
        "classifier_name": "edge_relay",
        "data": {
            "workload": 0.65,
            "confidence": 0.89,
            "band_powers": {"delta": 0.12, "theta": 0.25, "alpha": 0.35, ...},
            "metrics": {"frontal_theta": 0.22, "theta_beta_ratio": 1.38, ...}
        }
    }

    Azure LSTM prediction:
    {
        "prediction_type": "workload_azure_lstm",
        "classifier_name": "azure_ml_lstm_v2",
        "data": {
            "workload_prediction": 0.72,
            "confidence": 0.94,
            "model_uncertainty": 0.06
        }
    }

    Azure emotion model:
    {
        "prediction_type": "emotion_azure",
        "classifier_name": "azure_emotion_transformer",
        "data": {
            "emotion": "focused",
            "valence": 0.7,
            "arousal": 0.6,
            "confidence": 0.88
        }
    }
    """

    __tablename__ = "predictions"

    timestamp = Column(DateTime(timezone=True), nullable=False, primary_key=True)
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(
        PGUUID(as_uuid=True), ForeignKey("sessions.session_id"), nullable=False, index=True
    )
    user_id = Column(String(100), nullable=False, index=True)  # Denormalized for fast queries

    # Extensible prediction schema
    prediction_type = Column(String(50), nullable=False, index=True)
    classifier_name = Column(String(100), nullable=False)

    # Flexible data storage for any prediction schema
    data = Column(JSONB, nullable=False)

    # Optional metadata (extract commonly queried fields)
    confidence = Column(Float, nullable=True)
    classifier_version = Column(String(50), nullable=True)
    processing_time_ms = Column(Float, nullable=True)

    def __repr__(self):
        return f"<Prediction {self.timestamp} type={self.prediction_type}>"


class RawSample(Base):  # type: ignore[misc,valid-type]
    """Raw EEG samples - REQUIRED for Azure ML, visualization, analysis.

    TimescaleDB hypertable for time-series optimization.

    Use cases:
    - Azure ML models that operate on raw EEG (not just features)
    - Real-time visualization dashboards
    - Signal quality monitoring
    - Offline analysis and research

    Metadata (sampling_rate, channel_names) stored in Session.device_info.
    Samples only store channel values for efficiency.

    Data format:
    {
        "channels": [0.1, 0.2, -0.3, 0.15, 0.22, -0.1, 0.3]
    }

    To get full context, join with Session:
        SELECT s.data, sess.device_info->>'sampling_rate', sess.device_info->>'channel_names'
        FROM raw_samples s
        JOIN sessions sess ON s.session_id = sess.session_id
        WHERE s.user_id = 'user_123'

    Storage: ~56 bytes per sample (vs ~200 bytes with redundant metadata)
    Volume: ~7 KB/s per user at 128 Hz, 7 channels
    """

    __tablename__ = "raw_samples"

    timestamp = Column(DateTime(timezone=True), nullable=False, primary_key=True)
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(
        PGUUID(as_uuid=True), ForeignKey("sessions.session_id"), nullable=False, index=True
    )
    user_id = Column(String(100), nullable=False, index=True)  # Denormalized for fast queries

    # Raw EEG channel values only (metadata in Session.device_info)
    data = Column(JSONB, nullable=False)

    def __repr__(self):
        return f"<RawSample {self.timestamp} user={self.user_id}>"
