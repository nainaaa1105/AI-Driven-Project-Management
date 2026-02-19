"""Pydantic schemas for chat message request/response."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class MessageCreate(BaseModel):
    """Incoming chat message from the frontend."""
    content: str


class MessageResponse(BaseModel):
    """Full message record returned to the frontend."""
    id: int
    content: str
    sender: str
    ai_response: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AIProcessingResult(BaseModel):
    """Result returned after AI pipeline processes a message."""
    summary: str
    task_created: bool
    task_id: Optional[int] = None
    similarity_label: str = "NEW"
    risk_score: float = 0.0
    risk_level: str = "Low"
    risk_reason: str = ""
    alert: Optional[str] = None
    domain: str = "General"
    urgency: str = "normal"
    executive_report: Optional[dict] = None


class CommandResult(BaseModel):
    """Result returned when a chat command (update/delete) is detected."""
    action: str          # "update" | "delete"
    task_id: int
    message: str
    ok: bool = True
