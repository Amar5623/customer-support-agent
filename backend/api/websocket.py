# backend/api/websocket.py

import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manages active WebSocket connections per session.

    When CRM approves/rejects a request, it calls notify_session()
    with the session_id — if the customer is online, they get
    the update instantly in their chat.
    """

    def __init__(self):
        # session_id → WebSocket
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[session_id] = websocket
        logger.info(f"WebSocket connected — session={session_id}")

    def disconnect(self, session_id: str) -> None:
        self._connections.pop(session_id, None)
        logger.info(f"WebSocket disconnected — session={session_id}")

    async def notify_session(self, session_id: str, payload: dict) -> bool:
        """
        Send a message to a specific session if online.
        Returns True if delivered, False if session not connected.
        """
        ws = self._connections.get(session_id)
        if not ws:
            return False
        try:
            await ws.send_json(payload)
            logger.info(f"WebSocket notification sent — session={session_id}")
            return True
        except Exception as e:
            logger.warning(f"WebSocket send failed — session={session_id}: {e}")
            self.disconnect(session_id)
            return False

    def is_online(self, session_id: str) -> bool:
        return session_id in self._connections


# Module-level singleton
ws_manager = WebSocketManager()