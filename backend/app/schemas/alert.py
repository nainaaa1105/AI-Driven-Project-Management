"""Pydantic schemas for alerts."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class AlertOut(BaseModel):
    """Alert record returned to the frontend."""
    id: int
    message: str
    level: str
    task_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True
