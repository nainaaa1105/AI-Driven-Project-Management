"""
chat.py — POST /messages
=========================
Receives a raw chat message, runs the full ML-1 → ML-2 → ML-3 pipeline,
saves the message + AI response to the DB, and returns the analysis result.

Also intercepts special commands:
  • "update task <id>: <new title>"   → updates the task title
  • "delete task <id>"               → deletes the task
"""

import json
import re
import logging
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.message import Message
from app.schemas.message import MessageCreate, AIProcessingResult
from app.services.ai_orchestrator import orchestrator
from app.services.task_service import (
    get_task_by_id,
    update_task_title,
    delete_task,
)

router = APIRouter(tags=["Chat"])
logger = logging.getLogger("api.chat")

# ── Regex patterns for chat commands ──────────────────────────────────
_UPDATE_RE = re.compile(
    r"^update\s+task\s+#?(\d+)\s*:\s*(.+)", re.IGNORECASE
)
_DELETE_RE = re.compile(
    r"^delete\s+task\s+#?(\d+)\s*$", re.IGNORECASE
)


@router.post("/messages")
def send_message(payload: MessageCreate, db: Session = Depends(get_db)):
    """
    Accept a chat message. If it matches a command pattern (update/delete),
    handle it directly; otherwise run the full AI pipeline.
    """
    text = payload.content.strip()

    # ── 0. Persist the incoming message ─────────────────────────────
    db_message = Message(content=text, sender="user")
    db.add(db_message)
    db.commit()
    db.refresh(db_message)

    # ── 1. Check for DELETE command ─────────────────────────────────
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

    # ── 2. Check for UPDATE command ─────────────────────────────────
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

    # ── 3. Default: run the full ML pipeline ────────────────────────
    logger.info(f"Processing message #{db_message.id}: {text[:80]}…")
    result = orchestrator.process_message(text, db)

    ai_text = _build_ai_response_text(result)
    db_message.ai_response = ai_text
    db.commit()

    return AIProcessingResult(**result)


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
