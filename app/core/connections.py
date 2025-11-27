"""WebSocket connection management.

Industry-standard connection manager pattern for FastAPI WebSockets.
"""

import logging
from typing import Dict
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for edge relays and consumers.

    Tracks active connections and provides methods to send messages.
    Handles dead connection cleanup automatically.
    """

    def __init__(self):
        """Initialize connection manager."""
        self.edges: Dict[str, WebSocket] = {}       # user_id -> edge relay WebSocket
        self.consumers: Dict[str, WebSocket] = {}   # consumer_id -> consumer WebSocket

    async def connect_edge(self, user_id: str, websocket: WebSocket):
        """Register an edge relay connection.

        Args:
            user_id: User identifier
            websocket: WebSocket connection
        """
        self.edges[user_id] = websocket
        logger.info(f"Edge relay connected: {user_id}")

    def disconnect_edge(self, user_id: str):
        """Remove an edge relay connection.

        Args:
            user_id: User identifier
        """
        if user_id in self.edges:
            del self.edges[user_id]
            logger.info(f"Edge relay disconnected: {user_id}")

    async def send_to_edge(self, user_id: str, message: dict) -> bool:
        """Send message to edge relay.

        Args:
            user_id: User identifier
            message: Message to send

        Returns:
            True if sent successfully, False if connection dead
        """
        if user_id not in self.edges:
            return False

        try:
            await self.edges[user_id].send_json(message)
            return True
        except Exception as e:
            logger.warning(f"Failed to send to edge {user_id}: {e}")
            # Dead connection, cleanup
            self.disconnect_edge(user_id)
            return False

    async def connect_consumer(self, consumer_id: str, websocket: WebSocket):
        """Register a consumer connection.

        Args:
            consumer_id: Consumer identifier
            websocket: WebSocket connection
        """
        self.consumers[consumer_id] = websocket
        logger.info(f"Consumer connected: {consumer_id}")

    def disconnect_consumer(self, consumer_id: str):
        """Remove a consumer connection.

        Args:
            consumer_id: Consumer identifier
        """
        if consumer_id in self.consumers:
            del self.consumers[consumer_id]
            logger.info(f"Consumer disconnected: {consumer_id}")

    def get_stats(self) -> dict:
        """Get connection statistics.

        Returns:
            Dictionary with connection counts
        """
        return {
            "active_edge_connections": len(self.edges),
            "active_consumer_connections": len(self.consumers),
            "connected_users": list(self.edges.keys()),
        }
