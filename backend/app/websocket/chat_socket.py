"""
chat_socket.py — WebSocket endpoints for real-time communication
=================================================================
Two WebSocket endpoints:
  1. /ws/chat/{channel_id} — Per-channel chat (ML pipeline)
  2. /ws/workspace/{workspace_id} — Workspace-level real-time events
     (chat messages, member updates, workspace deletion)
"""

import json
import logging
from typing import Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.database import SessionLocal
from app.models.message import Message
from app.models.channel import Channel
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.auth.jwt_handler import decode_access_token
from app.services.ai_orchestrator import orchestrator

router = APIRouter()
logger = logging.getLogger("ws.chat")


# ─── Channel-level connection manager (existing) ──────────────────────────
class ChannelConnectionManager:
    """Track active WebSocket connections per channel and broadcast messages."""

    def __init__(self):
        self.channels: Dict[int, List[tuple]] = {}

    async def connect(self, channel_id: int, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if channel_id not in self.channels:
            self.channels[channel_id] = []
        self.channels[channel_id].append((websocket, user_id))
        logger.info(f"WS connected: user {user_id} -> channel {channel_id} "
                     f"({len(self.channels[channel_id])} active)")

    def disconnect(self, channel_id: int, websocket: WebSocket):
        if channel_id in self.channels:
            self.channels[channel_id] = [
                (ws, uid) for ws, uid in self.channels[channel_id] if ws != websocket
            ]
            if not self.channels[channel_id]:
                del self.channels[channel_id]
        logger.info(f"WS disconnected from channel {channel_id}")

    async def broadcast_to_channel(self, channel_id: int, message: str):
        if channel_id not in self.channels:
            return
        for ws, _ in self.channels[channel_id]:
            try:
                await ws.send_text(message)
            except Exception:
                pass

    async def send_to_user_in_channel(self, channel_id: int, user_id: int, message: str):
        if channel_id not in self.channels:
            return
        for ws, uid in self.channels[channel_id]:
            if uid == user_id:
                try:
                    await ws.send_text(message)
                except Exception:
                    pass


# ─── Workspace-level connection manager (NEW) ─────────────────────────────
class WorkspaceConnectionManager:
    """Track active WebSocket connections per workspace for real-time events."""

    def __init__(self):
        # workspace_id -> list of (websocket, user_id, user_name) tuples
        self.workspaces: Dict[int, List[tuple]] = {}

    async def connect(self, workspace_id: int, websocket: WebSocket, user_id: int, user_name: str):
        await websocket.accept()
        if workspace_id not in self.workspaces:
            self.workspaces[workspace_id] = []
        self.workspaces[workspace_id].append((websocket, user_id, user_name))
        logger.info(f"WS workspace connected: user {user_id} -> workspace {workspace_id} "
                     f"({len(self.workspaces[workspace_id])} active)")

    def disconnect(self, workspace_id: int, websocket: WebSocket):
        if workspace_id in self.workspaces:
            self.workspaces[workspace_id] = [
                (ws, uid, uname) for ws, uid, uname in self.workspaces[workspace_id] if ws != websocket
            ]
            if not self.workspaces[workspace_id]:
                del self.workspaces[workspace_id]

    async def broadcast(self, workspace_id: int, message: str):
        """Send a text frame to every client in a workspace."""
        if workspace_id not in self.workspaces:
            return
        for ws, _, _ in self.workspaces[workspace_id]:
            try:
                await ws.send_text(message)
            except Exception:
                pass

    async def disconnect_all(self, workspace_id: int, reason: str = "workspace_deleted"):
        """Close all connections for a workspace (used on deletion)."""
        if workspace_id not in self.workspaces:
            return
        msg = json.dumps({"type": "workspace_deleted", "workspace_id": workspace_id, "reason": reason})
        connections = list(self.workspaces.get(workspace_id, []))
        for ws, _, _ in connections:
            try:
                await ws.send_text(msg)
                await ws.close(code=4010, reason=reason)
            except Exception:
                pass
        self.workspaces.pop(workspace_id, None)

    def get_online_user_ids(self, workspace_id: int) -> list:
        """Return list of user_ids currently connected to a workspace."""
        if workspace_id not in self.workspaces:
            return []
        return list(set(uid for _, uid, _ in self.workspaces[workspace_id]))


manager = ChannelConnectionManager()
ws_manager = WorkspaceConnectionManager()


def _authenticate_ws(token: str, db):
    """Validate JWT and return the User, or None."""
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
        return db.query(User).filter(User.id == user_id).first()
    except Exception:
        return None


def _check_workspace_membership(user_id: int, workspace_id: int, db) -> bool:
    """Verify user is a member of the workspace."""
    member = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        .first()
    )
    return member is not None


def _check_workspace_open(workspace_id: int, db) -> bool:
    """Check if workspace has open access."""
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    return ws is not None and ws.access_type == "open"


# ─── Workspace-level WebSocket endpoint (NEW) ─────────────────────────────
@router.websocket("/ws/workspace/{workspace_id}")
async def websocket_workspace(websocket: WebSocket, workspace_id: int, token: str = Query(None)):
    """
    Workspace-level WebSocket for real-time events.

    Connection: ws://host/ws/workspace/{workspace_id}?token=<JWT>

    Server → Client events:
      { "type": "chat_message", "sender", "sender_id", "content", ... }
      { "type": "ai_response", ... }
      { "type": "member_joined", "user_id", "user_name", "role" }
      { "type": "member_left", "user_id" }
      { "type": "workspace_deleted", "workspace_id" }
      { "type": "presence_update", "online_users": [...] }

    Client → Server:
      { "type": "chat", "content": "..." }
      { "type": "ping" }
    """
    db = SessionLocal()
    try:
        if not token:
            await websocket.close(code=4001, reason="Missing authentication token")
            return

        user = _authenticate_ws(token, db)
        if not user:
            await websocket.close(code=4001, reason="Invalid or expired token")
            return

        # Check workspace exists
        workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if not workspace:
            await websocket.close(code=4004, reason="Workspace not found")
            return

        # Require actual membership — WebSocket must never auto-join.
        # Even open workspaces require the user to have joined first via
        # POST /workspaces/{id}/join before they can connect.
        is_member = _check_workspace_membership(user.id, workspace_id, db)
        if not is_member:
            await websocket.close(code=4003, reason="Not a member of this workspace")
            return

        user_id = user.id
        user_name = user.name
    finally:
        db.close()

    # Connection accepted
    await ws_manager.connect(workspace_id, websocket, user_id, user_name)
    logger.info(f"WS connected: user {user_id} ({user_name}) → workspace {workspace_id}")

    # Broadcast presence update to all clients
    online_ids = ws_manager.get_online_user_ids(workspace_id)
    await ws_manager.broadcast(workspace_id, json.dumps({
        "type": "presence_update",
        "online_users": online_ids,
    }))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {"type": "chat", "content": raw}

            msg_type = data.get("type", "chat")

            if msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                continue

            if msg_type == "chat":
                # Chat messages are now sent via REST /messages which
                # broadcasts to WS after processing the AI pipeline.
                # If a client still sends "chat" over WS, just ignore
                # to prevent double processing.
                logger.debug(f"WS chat message from user {user_id} ignored (use REST /messages)")
                continue

    except WebSocketDisconnect:
        ws_manager.disconnect(workspace_id, websocket)
        logger.info(f"WS disconnected: user {user_id} from workspace {workspace_id}")
        # Broadcast updated presence
        online_ids = ws_manager.get_online_user_ids(workspace_id)
        await ws_manager.broadcast(workspace_id, json.dumps({
            "type": "presence_update",
            "online_users": online_ids,
        }))


# ─── Channel-level WebSocket endpoint (existing) ──────────────────────────
@router.websocket("/ws/chat/{channel_id}")
async def websocket_chat(websocket: WebSocket, channel_id: int, token: str = Query(None)):
    """
    WebSocket endpoint for real-time channel chat.

    Connection: ws://host/ws/chat/{channel_id}?token=<JWT>

    Protocol (text frames, JSON):
      Client → Server:  { "content": "Login is broken ..." }
      Server → Client:  { "type": "user_message"|"ai_response"|"task_notification", ... }
    """
    db = SessionLocal()
    try:
        if not token:
            await websocket.close(code=4001, reason="Missing authentication token")
            return

        user = _authenticate_ws(token, db)
        if not user:
            await websocket.close(code=4001, reason="Invalid or expired token")
            return

        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        if not channel:
            await websocket.close(code=4004, reason="Channel not found")
            return

        if not _check_workspace_membership(user.id, channel.workspace_id, db):
            await websocket.close(code=4003, reason="Not a member of this workspace")
            return

        workspace_id = channel.workspace_id
    finally:
        db.close()

    await manager.connect(channel_id, websocket, user.id)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                content = data.get("content", raw)
            except json.JSONDecodeError:
                content = raw

            db = SessionLocal()
            try:
                db_msg = Message(
                    content=content,
                    sender=user.name,
                    sender_id=user.id,
                    workspace_id=workspace_id,
                    channel_id=channel_id,
                )
                db.add(db_msg)
                db.commit()
                db.refresh(db_msg)

                user_msg = json.dumps({
                    "type": "user_message",
                    "message_id": db_msg.id,
                    "sender": user.name,
                    "sender_id": user.id,
                    "content": content,
                    "channel_id": channel_id,
                    "created_at": db_msg.created_at.isoformat() if db_msg.created_at else None,
                })
                await manager.broadcast_to_channel(channel_id, user_msg)

                result = orchestrator.process_message(
                    content, db,
                    workspace_id=workspace_id,
                    channel_id=channel_id,
                    sender_id=user.id,
                    message_id=db_msg.id,
                )

                db_msg.ai_response = json.dumps(result, default=str)
                db.commit()

                ai_response = json.dumps({
                    "type": "ai_response",
                    "message_id": db_msg.id,
                    "channel_id": channel_id,
                    **result,
                }, default=str)
                await manager.broadcast_to_channel(channel_id, ai_response)

                if result.get("task_id"):
                    task_notification = json.dumps({
                        "type": "task_notification",
                        "channel_id": channel_id,
                        "task_id": result["task_id"],
                        "task_created": result.get("task_created", False),
                        "similarity_label": result.get("similarity_label", "NEW"),
                        "summary": result.get("summary", ""),
                        "risk_level": result.get("risk_level", "Low"),
                    })
                    await manager.broadcast_to_channel(channel_id, task_notification)

            finally:
                db.close()

    except WebSocketDisconnect:
        manager.disconnect(channel_id, websocket)
