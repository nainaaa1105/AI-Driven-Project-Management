"""
channels.py — Channel CRUD APIs
=================================
Create, list, and manage channels within workspaces.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.channel import Channel
from app.auth.dependencies import get_current_user, require_workspace_member, require_workspace_role
from app.schemas.channel import ChannelCreate, ChannelOut

router = APIRouter(tags=["Channels"])
logger = logging.getLogger("api.channels")


@router.post(
    "/workspaces/{workspace_id}/channels",
    response_model=ChannelOut,
    status_code=status.HTTP_201_CREATED,
)
def create_channel(
    workspace_id: int,
    payload: ChannelCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new channel in a workspace (admin or member)."""
    require_workspace_role(workspace_id, user, db, ["admin", "member"])

    channel = Channel(
        workspace_id=workspace_id,
        name=payload.name.strip(),
        description=payload.description or "",
        created_by=user.id,
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    logger.info(f"Channel created: #{channel.name} (id={channel.id}) in workspace {workspace_id}")
    return channel


@router.get(
    "/workspaces/{workspace_id}/channels",
    response_model=List[ChannelOut],
)
def list_channels(
    workspace_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all channels in a workspace."""
    require_workspace_member(workspace_id, user, db)

    return (
        db.query(Channel)
        .filter(Channel.workspace_id == workspace_id)
        .order_by(Channel.created_at)
        .all()
    )


@router.get(
    "/channels/{channel_id}",
    response_model=ChannelOut,
)
def get_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a single channel by ID (requires workspace membership)."""
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    require_workspace_member(channel.workspace_id, user, db)
    return channel


@router.delete("/channels/{channel_id}", status_code=status.HTTP_200_OK)
def delete_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a channel (admin only). Cannot delete the last channel in a workspace."""
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    require_workspace_role(channel.workspace_id, user, db, ["admin"])

    # Prevent deleting the last channel
    channel_count = (
        db.query(Channel)
        .filter(Channel.workspace_id == channel.workspace_id)
        .count()
    )
    if channel_count <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the last channel in a workspace")

    db.delete(channel)
    db.commit()
    return {"ok": True, "message": f"Channel #{channel.name} deleted"}
