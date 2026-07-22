"""
WebSocket connection manager for real-time notifications, appointment updates,
and chatbot stream progress.
"""

import logging
from typing import Dict, List, Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class WebSocketConnectionManager:
    def __init__(self) -> None:
        # Structure: tenant_id -> user_id -> List[WebSocket]
        self._active_connections: Dict[str, Dict[str, List[WebSocket]]] = {}

    async def connect(self, websocket: WebSocket, tenant_id: str, user_id: str) -> None:
        """Register a new WebSocket connection."""
        await websocket.accept()
        
        if tenant_id not in self._active_connections:
            self._active_connections[tenant_id] = {}
            
        if user_id not in self._active_connections[tenant_id]:
            self._active_connections[tenant_id][user_id] = []
            
        self._active_connections[tenant_id][user_id].append(websocket)
        logger.info(
            "[WS] Client connected: tenant=%s, user=%s (total connections: %d)",
            tenant_id,
            user_id,
            len(self._active_connections[tenant_id][user_id]),
        )

    def disconnect(self, websocket: WebSocket, tenant_id: str, user_id: str) -> None:
        """Remove a disconnected WebSocket connection."""
        if tenant_id in self._active_connections:
            if user_id in self._active_connections[tenant_id]:
                if websocket in self._active_connections[tenant_id][user_id]:
                    self._active_connections[tenant_id][user_id].remove(websocket)
                if not self._active_connections[tenant_id][user_id]:
                    self._active_connections[tenant_id].pop(user_id)
            if not self._active_connections[tenant_id]:
                self._active_connections.pop(tenant_id)
        logger.info("[WS] Client disconnected: tenant=%s, user=%s", tenant_id, user_id)

    async def send_personal_message(self, message: dict, tenant_id: str, user_id: str) -> None:
        """Send a real-time message to all active sessions of a specific user."""
        connections = self._active_connections.get(tenant_id, {}).get(user_id, [])
        if not connections:
            logger.debug("[WS] No active connection for tenant=%s, user=%s.", tenant_id, user_id)
            return

        logger.debug("[WS] Sending message to user=%s on tenant=%s", user_id, tenant_id)
        for websocket in list(connections):
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning("[WS] Failed to send JSON message to user=%s: %s", user_id, e)
                self.disconnect(websocket, tenant_id, user_id)

    async def broadcast_to_tenant(self, message: dict, tenant_id: str) -> None:
        """Broadcast a message to all connected clients within a tenant workspace."""
        user_connections = self._active_connections.get(tenant_id, {})
        if not user_connections:
            return

        logger.debug("[WS] Broadcasting message to all users on tenant=%s", tenant_id)
        for user_id, connections in list(user_connections.items()):
            for websocket in list(connections):
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.warning("[WS] Failed to send JSON broadcast to user=%s: %s", user_id, e)
                    self.disconnect(websocket, tenant_id, user_id)


_ws_manager_instance: Optional[WebSocketConnectionManager] = None

def get_websocket_manager() -> WebSocketConnectionManager:
    """Return the process-wide WebSocket connection manager singleton."""
    global _ws_manager_instance
    if _ws_manager_instance is None:
        _ws_manager_instance = WebSocketConnectionManager()
    return _ws_manager_instance
