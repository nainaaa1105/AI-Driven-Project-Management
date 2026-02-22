"""Pydantic schemas for workspaces and workspace members."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class WorkspaceCreate(BaseModel):
    """Payload for creating a new workspace."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = ""
    access_type: Optional[str] = Field("private", pattern="^(private|open)$")


class WorkspaceOut(BaseModel):
    """Workspace record returned to the client."""
    id: int
    name: str
    description: Optional[str] = ""
    access_type: str = "private"
    created_by: int
    created_at: datetime

    class Config:
        from_attributes = True


class WorkspaceLookupOut(BaseModel):
    """Public workspace info returned to any authenticated user (no membership required)."""
    id: int
    name: str
    description: Optional[str] = ""
    access_type: str = "private"

    class Config:
        from_attributes = True


class WorkspaceMemberOut(BaseModel):
    """Workspace member record (enriched with user name)."""
    id: int
    workspace_id: int
    user_id: int
    role: str
    name: Optional[str] = None
    email: Optional[str] = None
    joined_at: datetime

    class Config:
        from_attributes = True


class AddMemberRequest(BaseModel):
    """Payload for adding a member to a workspace."""
    user_id: int
    role: str = Field("member", pattern="^(admin|member|viewer)$")
