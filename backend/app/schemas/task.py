"""Pydantic schemas for tasks."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class TaskOut(BaseModel):
    """Task record returned to the frontend."""
    id: int
    title: str
    description: Optional[str] = ""
    status: str = "open"
    risk_score: Optional[float] = 0.0
    risk_level: Optional[str] = "Low"
    risk_reason: Optional[str] = ""
    domain: Optional[str] = "General"
    urgency: Optional[str] = "normal"
    similarity_label: Optional[str] = "NEW"
    linked_task_id: Optional[int] = None
    update_notes: Optional[str] = ""
    workspace_id: Optional[int] = None
    channel_id: Optional[int] = None
    assigned_user_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TaskUpdatePayload(BaseModel):
    """Payload for PATCH /tasks/{id} — user‑driven update."""
    update_note: Optional[str] = None
    domains: Optional[List[str]] = None
    urgency: Optional[str] = None
    status: Optional[str] = None
    assigned_user_id: Optional[int] = None
