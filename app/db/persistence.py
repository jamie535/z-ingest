"""Database persistence layer with batched async writes.

Batching prevents blocking WebSocket on every DB write.
Performance: ~1ms per sample (amortized) vs 10-50ms per individual write.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID
from collections import deque

from .models import Prediction, RawSample

logger = logging.getLogger(__name__)


class PersistenceManager:
    """Manages batched writes to database for performance.

    Flushes when:
    - Buffer reaches batch_size (default 50)
    - flush_interval seconds have passed (default 5s)
    - Graceful shutdown (stop() called)
    """

    def __init__(
        self,
        db_manager,
        batch_size: int = 50,
        flush_interval: float = 5.0,
    ):
        """Initialize persistence manager.

        Args:
            db_manager: Database manager instance
            batch_size: Number of records to batch before writing
            flush_interval: Time in seconds between automatic flushes
        """
        self.db = db_manager
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        # Buffers for each table
        self.prediction_buffer: deque = deque()
        self.raw_sample_buffer: deque = deque()

        # Background task for periodic flushing
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Start the background flush task."""
        if self._running:
            return

        self._running = True
        self._flush_task = asyncio.create_task(self._periodic_flush())
        logger.info("PersistenceManager started (batch_size=%d, interval=%.1fs)",
                   self.batch_size, self.flush_interval)

    async def stop(self):
        """Stop the background flush task and flush remaining data."""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Final flush
        await self.flush_all()
        logger.info("PersistenceManager stopped (flushed remaining data)")

    async def _periodic_flush(self):
        """Periodically flush buffers to database."""
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                await self.flush_all()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic flush: {e}", exc_info=True)

    async def add_prediction(
        self,
        timestamp: datetime,
        session_id: UUID,
        user_id: str,
        prediction_type: str,
        classifier_name: str,
        data: Dict[str, Any],
        confidence: Optional[float] = None,
        classifier_version: Optional[str] = None,
        processing_time_ms: Optional[float] = None,
    ):
        """Add a prediction to the buffer (features or Azure ML predictions).

        Will auto-flush when batch_size is reached.

        Args:
            timestamp: Prediction timestamp
            session_id: Session UUID
            user_id: User identifier
            prediction_type: Type (e.g., "workload_edge", "emotion_azure")
            classifier_name: Source (e.g., "edge_relay", "azure_ml_lstm_v2")
            data: Complete prediction data (flexible JSONB)
            confidence: Confidence score (optional)
            classifier_version: Classifier version (optional)
            processing_time_ms: Processing time (optional)
        """
        prediction = {
            "timestamp": timestamp,
            "session_id": session_id,
            "user_id": user_id,
            "prediction_type": prediction_type,
            "classifier_name": classifier_name,
            "data": data,
            "confidence": confidence,
            "classifier_version": classifier_version,
            "processing_time_ms": processing_time_ms,
        }
        self.prediction_buffer.append(prediction)

        if len(self.prediction_buffer) >= self.batch_size:
            await self.flush_predictions()

    async def add_raw_sample(
        self,
        timestamp: datetime,
        session_id: UUID,
        user_id: str,
        data: Dict[str, Any],
    ):
        """Add a raw EEG sample to the buffer.

        Will auto-flush when batch_size is reached.

        Args:
            timestamp: Sample timestamp
            session_id: Session UUID
            user_id: User identifier
            data: Raw channel data (e.g., {"channels": [0.1, 0.2, ...]})
        """
        sample = {
            "timestamp": timestamp,
            "session_id": session_id,
            "user_id": user_id,
            "data": data,
        }
        self.raw_sample_buffer.append(sample)

        if len(self.raw_sample_buffer) >= self.batch_size:
            await self.flush_raw_samples()

    async def flush_predictions(self):
        """Flush prediction buffer to database."""
        if not self.prediction_buffer:
            return

        records = list(self.prediction_buffer)
        self.prediction_buffer.clear()

        try:
            async with self.db.get_session() as session:
                session.add_all([Prediction(**record) for record in records])
                await session.commit()
            logger.debug(f"Flushed {len(records)} predictions to database")
        except Exception as e:
            logger.error(f"Error flushing predictions: {e}", exc_info=True)
            # Re-add to buffer for retry
            self.prediction_buffer.extend(records)

    async def flush_raw_samples(self):
        """Flush raw sample buffer to database."""
        if not self.raw_sample_buffer:
            return

        records = list(self.raw_sample_buffer)
        self.raw_sample_buffer.clear()

        try:
            async with self.db.get_session() as session:
                session.add_all([RawSample(**record) for record in records])
                await session.commit()
            logger.debug(f"Flushed {len(records)} raw samples to database")
        except Exception as e:
            logger.error(f"Error flushing raw samples: {e}", exc_info=True)
            # Re-add to buffer for retry
            self.raw_sample_buffer.extend(records)

    async def flush_all(self):
        """Flush all buffers to database."""
        await self.flush_predictions()
        await self.flush_raw_samples()

    def get_stats(self) -> Dict[str, Any]:
        """Get persistence manager statistics.

        Returns:
            Dictionary with buffer stats
        """
        return {
            "prediction_buffer_size": len(self.prediction_buffer),
            "raw_sample_buffer_size": len(self.raw_sample_buffer),
            "batch_size": self.batch_size,
            "flush_interval": self.flush_interval,
            "running": self._running,
        }
