"""
chat_socket.py — WebSocket /ws/chat
=====================================
Real-time chat via WebSocket.  Each incoming text frame is treated as a
raw message, run through the full ML pipeline, and the AI result is
pushed back to all connected clients.
"""

import json
import logging
from typing import List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.message import Message
from app.services.ai_orchestrator import orchestrator

router = APIRouter()
logger = logging.getLogger("ws.chat")


class ConnectionManager:
    """Track active WebSocket connections and broadcast messages."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected — {len(self.active_connections)} active")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected — {len(self.active_connections)} active")

    async def broadcast(self, message: str):
        """Send a text frame to every connected client."""
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass


manager = ConnectionManager()


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket endpoint for real-time chat.

    Protocol (text frames, JSON):
      Client → Server:  { "content": "Login is broken …" }
      Server → Client:  { "type": "ai_response", ...pipeline result... }
    """
    await manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                content = data.get("content", raw)
            except json.JSONDecodeError:
                content = raw

            # Run ML pipeline in a fresh DB session
            db = SessionLocal()
            try:
                # Save user message
                db_msg = Message(content=content, sender="user")
                db.add(db_msg)
                db.commit()
                db.refresh(db_msg)

                # AI pipeline
                result = orchestrator.process_message(content, db)

                # Save AI response
                db_msg.ai_response = json.dumps(result, default=str)
                db.commit()

                # Broadcast to all connected clients
                response = {
                    "type": "ai_response",
                    "message_id": db_msg.id,
                    **result,
                }
                await manager.broadcast(json.dumps(response, default=str))

            finally:
                db.close()

    except WebSocketDisconnect:
        manager.disconnect(websocket)
