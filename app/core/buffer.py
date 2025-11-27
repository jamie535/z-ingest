"""In-memory buffer for real-time EEG stream data.

Thread-safe circular buffer for storing latest samples from active sessions.
Enables low-latency real-time queries for MCP tools, dashboards, and consumers.

Supports:
- Preprocessed features (workload, band_powers, metrics)
- Raw EEG samples (channels)
- Time-range queries
- Per-user filtering
"""

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from uuid import UUID


class StreamBuffer:
    """Thread-safe circular buffer for real-time stream data.

    Stores the latest N samples for quick access.
    Uses collections.deque for O(1) append and automatic size limiting.
    Thread-safe via asyncio.Lock.
    """

    def __init__(self, maxlen: int = 1000):
        """Initialize stream buffer.

        Args:
            maxlen: Maximum number of samples to store (oldest are auto-dropped)
        """
        self.maxlen = maxlen
        self._buffer: deque = deque(maxlen=maxlen)
        self._lock = asyncio.Lock()

    async def add_sample(
        self,
        timestamp: datetime,
        data: Any,
        session_id: UUID,
        user_id: str,
        sample_type: str = "features",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Add a sample to the buffer.

        Args:
            timestamp: Sample timestamp (timezone-aware)
            data: Data to store
                - "features": Dict with workload, band_powers, metrics
                - "raw": Dict with channels array
            session_id: Session UUID
            user_id: User identifier
            sample_type: Type of data ("features" or "raw")
            metadata: Optional additional metadata
        """
        async with self._lock:
            sample = {
                "timestamp": timestamp,
                "data": data,
                "session_id": session_id,
                "user_id": user_id,
                "sample_type": sample_type,
                "metadata": metadata or {},
            }
            self._buffer.append(sample)

    async def get_latest(self, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get the most recent sample.

        Args:
            user_id: Optional filter by user_id

        Returns:
            Latest sample dict or None if buffer is empty
        """
        async with self._lock:
            if not self._buffer:
                return None

            if user_id is None:
                return self._buffer[-1]

            # Search backwards for latest sample from this user
            for sample in reversed(self._buffer):
                if sample["user_id"] == user_id:
                    return sample

            return None

    async def get_last_n(
        self,
        n: int,
        user_id: Optional[str] = None,
        sample_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get the last N samples.

        Args:
            n: Number of samples to retrieve
            user_id: Optional filter by user_id
            sample_type: Optional filter by sample type ("features" or "raw")

        Returns:
            List of sample dicts (newest first)
        """
        async with self._lock:
            if not self._buffer:
                return []

            # Filter samples
            filtered = list(self._buffer)
            if user_id is not None:
                filtered = [s for s in filtered if s["user_id"] == user_id]
            if sample_type is not None:
                filtered = [s for s in filtered if s["sample_type"] == sample_type]

            # Return last n samples (newest first)
            return list(reversed(filtered[-n:]))

    async def get_range(
        self,
        start_time: datetime,
        end_time: datetime,
        user_id: Optional[str] = None,
        sample_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get samples within a time range.

        Args:
            start_time: Start of time range (timezone-aware)
            end_time: End of time range (timezone-aware)
            user_id: Optional filter by user_id
            sample_type: Optional filter by sample type

        Returns:
            List of samples in time range (oldest first)
        """
        async with self._lock:
            if not self._buffer:
                return []

            samples = []
            for sample in self._buffer:
                sample_ts = sample["timestamp"]
                # Ensure timezone-aware comparison
                if sample_ts.tzinfo is None:
                    sample_ts = sample_ts.replace(tzinfo=timezone.utc)

                if start_time <= sample_ts <= end_time:
                    if user_id is None or sample["user_id"] == user_id:
                        if sample_type is None or sample["sample_type"] == sample_type:
                            samples.append(sample)

            return samples

    async def clear(self, user_id: Optional[str] = None):
        """Clear the buffer.

        Args:
            user_id: Optional - only clear samples for this user
        """
        async with self._lock:
            if user_id is None:
                self._buffer.clear()
            else:
                # Remove only samples from this user
                self._buffer = deque(
                    (s for s in self._buffer if s["user_id"] != user_id),
                    maxlen=self.maxlen
                )

    async def get_stats(self) -> Dict[str, Any]:
        """Get buffer statistics.

        Returns:
            Dictionary with buffer stats (total_samples, unique_users, etc.)
        """
        async with self._lock:
            if not self._buffer:
                return {
                    "total_samples": 0,
                    "unique_users": 0,
                    "unique_sessions": 0,
                    "oldest_timestamp": None,
                    "newest_timestamp": None,
                    "buffer_capacity": self.maxlen,
                    "buffer_usage_percent": 0,
                }

            user_ids = set(s["user_id"] for s in self._buffer)
            session_ids = set(s["session_id"] for s in self._buffer)

            return {
                "total_samples": len(self._buffer),
                "unique_users": len(user_ids),
                "unique_sessions": len(session_ids),
                "oldest_timestamp": self._buffer[0]["timestamp"].isoformat(),
                "newest_timestamp": self._buffer[-1]["timestamp"].isoformat(),
                "buffer_capacity": self.maxlen,
                "buffer_usage_percent": round((len(self._buffer) / self.maxlen) * 100, 2),
            }
