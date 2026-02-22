"""Pydantic schemas for channels."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ChannelCreate(BaseModel):
    """Payload for creating a channel in a workspace."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = ""


class ChannelOut(BaseModel):
    """Channel record returned to the client."""
    id: int
    workspace_id: int
    name: str
    description: Optional[str] = ""
    created_by: int
    created_at: datetime

    class Config:
        from_attributes = True
