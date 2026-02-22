"""
messages.py — POST /messages, GET /messages/{channel_id}
=========================================================
Workspace-aware message API with AI orchestration trigger.
Broadcasts results to workspace WebSocket so other users see
messages in real time.
"""

import re
import json
import asyncio
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.message import Message
from app.models.channel import Channel
from app.auth.dependencies import get_current_user, require_workspace_member
from app.schemas.message import MessageCreate, MessageResponse, AIProcessingResult
from app.services.ai_orchestrator import orchestrator
from app.services.task_service import get_task_by_id, update_task_title, delete_task

router = APIRouter(tags=["Messages"])
logger = logging.getLogger("api.messages")


def _broadcast_to_workspace(workspace_id: int, payload: dict):
    """Fire-and-forget broadcast a message dict to all workspace WS clients."""
    try:
        from app.websocket.chat_socket import ws_manager
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(ws_manager.broadcast(workspace_id, json.dumps(payload, default=str)))
        else:
            loop.run_until_complete(ws_manager.broadcast(workspace_id, json.dumps(payload, default=str)))
    except Exception as exc:
        logger.debug(f"WS broadcast skipped: {exc}")

# ── Regex patterns for chat commands ──────────────────────────────────
_UPDATE_RE = re.compile(r"^update\s+task\s+#?(\d+)\s*:\s*(.+)", re.IGNORECASE)
_DELETE_RE = re.compile(r"^delete\s+task\s+#?(\d+)\s*$", re.IGNORECASE)


@router.post("/messages")
def send_message(
    payload: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Accept a chat message within a workspace channel.
    If it matches a command pattern (update/delete), handle it directly;
    otherwise run the full AI pipeline.
    """
    text = payload.content.strip()

    # Validate channel and workspace membership
    channel = None
    workspace_id = payload.workspace_id
    channel_id = payload.channel_id

    if channel_id:
        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")
        workspace_id = channel.workspace_id

    if workspace_id:
        require_workspace_member(workspace_id, user, db)

    # Persist the incoming message
    db_message = Message(
        content=text,
        sender=user.name,
        sender_id=user.id,
        workspace_id=workspace_id,
        channel_id=channel_id,
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)

    # Check for DELETE command
    m = _DELETE_RE.match(text)
    if m:
        task_id = int(m.group(1))
        task = get_task_by_id(db, task_id)
        if not task:
            resp = {"action": "delete", "task_id": task_id, "ok": False,
                    "message": f"Task #{task_id} not found."}
        else:
            delete_task(db, task_id)
            resp = {"action": "delete", "task_id": task_id, "ok": True,
                    "message": f"Task #{task_id} has been deleted."}
        db_message.ai_response = resp["message"]
        db.commit()
        return JSONResponse(content=resp)

    # Check for UPDATE command
    m = _UPDATE_RE.match(text)
    if m:
        task_id = int(m.group(1))
        new_title = m.group(2).strip()
        task = update_task_title(db, task_id, new_title)
        if not task:
            resp = {"action": "update", "task_id": task_id, "ok": False,
                    "message": f"Task #{task_id} not found."}
        else:
            resp = {"action": "update", "task_id": task_id, "ok": True,
                    "message": f"Task #{task_id} updated → \"{new_title}\"."}
        db_message.ai_response = resp["message"]
        db.commit()
        return JSONResponse(content=resp)

    # Default: run the full ML pipeline
    logger.info(f"Processing message #{db_message.id}: {text[:80]}…")
    result = orchestrator.process_message(
        text, db,
        workspace_id=workspace_id,
        channel_id=channel_id,
        sender_id=user.id,
        message_id=db_message.id,
    )

    ai_text = _build_ai_response_text(result)
    db_message.ai_response = ai_text
    db.commit()

    # Broadcast user message + AI response to workspace WS clients
    if workspace_id:
        _broadcast_to_workspace(workspace_id, {
            "type": "chat_message",
            "message_id": db_message.id,
            "sender": user.name,
            "sender_id": user.id,
            "content": text,
            "workspace_id": workspace_id,
            "created_at": db_message.created_at.isoformat() if db_message.created_at else None,
        })
        _broadcast_to_workspace(workspace_id, {
            "type": "ai_response",
            "message_id": db_message.id,
            "sender_id": user.id,
            "workspace_id": workspace_id,
            **result,
        })

    return AIProcessingResult(**result)


@router.get("/messages/{channel_id}", response_model=List[MessageResponse])
def get_channel_messages(
    channel_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Retrieve messages for a specific channel.
    Requires workspace membership.
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    require_workspace_member(channel.workspace_id, user, db)

    messages = (
        db.query(Message)
        .filter(Message.channel_id == channel_id)
        .order_by(Message.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return messages


def _build_ai_response_text(result: dict) -> str:
    """Compose a human-readable AI response string from the pipeline output."""
    parts = [f"Summary: {result.get('summary', 'N/A')}"]

    if result.get("task_created"):
        parts.append(f"Task #{result.get('task_id')} created ({result.get('similarity_label', 'NEW')})")
    else:
        parts.append(f"Task #{result.get('task_id')} updated ({result.get('similarity_label', 'DUPLICATE')})")

    parts.append(f"Risk: {result.get('risk_score', 0):.0%} ({result.get('risk_level', 'Low')})")

    if result.get("alert"):
        parts.append(result["alert"])

    return " | ".join(parts)
