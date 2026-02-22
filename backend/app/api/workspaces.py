"""
workspaces.py — Workspace CRUD APIs
=====================================
Create, list, and manage workspaces with membership and role enforcement.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.models.channel import Channel
from app.models.message import Message
from app.models.task import Task
from app.models.alert import Alert
from app.models.message_task_map import MessageTaskMap
from app.auth.dependencies import get_current_user, require_workspace_member, require_workspace_role
from app.schemas.workspace import WorkspaceCreate, WorkspaceOut, WorkspaceMemberOut, AddMemberRequest, WorkspaceLookupOut
from app.config import settings

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])
logger = logging.getLogger("api.workspaces")


@router.post("/", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Create a new workspace.
    The creating user is automatically added as admin.
    A #general channel is created by default.
    """
    workspace = Workspace(
        name=payload.name.strip(),
        description=payload.description or "",
        access_type=payload.access_type or "private",
        created_by=user.id,
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)

    # Add creator as admin
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role="admin",
    )
    db.add(member)

    # Also add AI Bot to the workspace if it exists
    ai_bot = db.query(User).filter(User.email == settings.AI_BOT_EMAIL).first()
    if ai_bot:
        bot_member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=ai_bot.id,
            role="member",
        )
        db.add(bot_member)

    # Create default #general channel
    general_channel = Channel(
        workspace_id=workspace.id,
        name="general",
        description="General discussion",
        created_by=user.id,
    )
    db.add(general_channel)
    db.commit()

    logger.info(f"Workspace created: '{workspace.name}' (id={workspace.id}) by user {user.id}")
    return workspace


@router.get("/", response_model=List[WorkspaceOut])
def list_workspaces(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all workspaces the current user belongs to."""
    member_rows = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.user_id == user.id)
        .all()
    )
    workspace_ids = [m.workspace_id for m in member_rows]
    if not workspace_ids:
        return []
    return (
        db.query(Workspace)
        .filter(Workspace.id.in_(workspace_ids))
        .order_by(Workspace.created_at.desc())
        .all()
    )


@router.get("/{workspace_id}", response_model=WorkspaceOut)
def get_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get workspace details (requires membership)."""
    require_workspace_member(workspace_id, user, db)
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


@router.get("/{workspace_id}/lookup", response_model=WorkspaceLookupOut)
def lookup_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Public lookup — any authenticated user can look up a workspace by ID.
    Returns limited info (name, description, access_type) without requiring membership.
    """
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


@router.get("/{workspace_id}/members", response_model=List[WorkspaceMemberOut])
def list_members(
    workspace_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all members of a workspace (enriched with user name & email)."""
    require_workspace_member(workspace_id, user, db)
    members = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.workspace_id == workspace_id)
        .all()
    )
    # Enrich with user names
    user_ids = [m.user_id for m in members]
    users_map = {}
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        users_map = {u.id: u for u in users}
    result = []
    for m in members:
        u = users_map.get(m.user_id)
        result.append(WorkspaceMemberOut(
            id=m.id,
            workspace_id=m.workspace_id,
            user_id=m.user_id,
            role=m.role,
            name=u.name if u else None,
            email=u.email if u else None,
            joined_at=m.joined_at,
        ))
    return result


@router.post("/{workspace_id}/members", response_model=WorkspaceMemberOut, status_code=status.HTTP_201_CREATED)
def add_member(
    workspace_id: int,
    payload: AddMemberRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Add a user to a workspace (admin only)."""
    require_workspace_role(workspace_id, user, db, ["admin"])

    # Check target user exists
    target_user = db.query(User).filter(User.id == payload.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check not already a member
    existing = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == payload.user_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="User is already a member")

    member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=payload.user_id,
        role=payload.role,
    )
    db.add(member)
    db.commit()
    db.refresh(member)

    logger.info(f"User {payload.user_id} added to workspace {workspace_id} as {payload.role}")
    return member


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_200_OK)
def remove_member(
    workspace_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Remove a member from a workspace (admin only, cannot remove self if last admin)."""
    require_workspace_role(workspace_id, user, db, ["admin"])

    member = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Prevent removing last admin
    if member.role == "admin":
        admin_count = (
            db.query(WorkspaceMember)
            .filter(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == "admin",
            )
            .count()
        )
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last admin")

    db.delete(member)
    db.commit()
    return {"ok": True, "message": f"User {user_id} removed from workspace {workspace_id}"}


@router.post("/{workspace_id}/join", response_model=WorkspaceMemberOut, status_code=status.HTTP_201_CREATED)
def join_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Self-join an open workspace.
    Only works if the workspace access_type is 'open'.
    Private workspaces require an admin to add the user.
    """
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if workspace.access_type != "open":
        raise HTTPException(status_code=403, detail="This workspace is private. Ask an admin to add you.")

    # Check not already a member
    existing = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="You are already a member of this workspace")

    member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=user.id,
        role="member",
    )
    db.add(member)
    db.commit()
    db.refresh(member)

    logger.info(f"User {user.id} self-joined open workspace {workspace_id}")

    return WorkspaceMemberOut(
        id=member.id,
        workspace_id=member.workspace_id,
        user_id=member.user_id,
        role=member.role,
        name=user.name,
        email=user.email,
        joined_at=member.joined_at,
    )


@router.delete("/{workspace_id}", status_code=status.HTTP_200_OK)
async def delete_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Delete a workspace (admin only).
    Broadcasts workspace_deleted to connected clients, then cascade deletes.
    """
    require_workspace_role(workspace_id, user, db, ["admin"])

    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    ws_name = workspace.name

    # Broadcast workspace_deleted to all connected WS clients BEFORE deleting
    try:
        from app.websocket.chat_socket import ws_manager
        import json
        await ws_manager.broadcast(workspace_id, json.dumps({
            "type": "workspace_deleted",
            "workspace_id": workspace_id,
            "workspace_name": ws_name,
        }))
        # Disconnect all WS clients from this workspace
        await ws_manager.disconnect_all(workspace_id)
    except Exception as exc:
        logger.debug(f"WS deletion broadcast skipped: {exc}")

    # Cascade delete related data
    # Get IDs for junction table cleanup
    task_ids = [t.id for t in db.query(Task.id).filter(Task.workspace_id == workspace_id).all()]
    message_ids = [m.id for m in db.query(Message.id).filter(Message.workspace_id == workspace_id).all()]
    if task_ids:
        db.query(MessageTaskMap).filter(MessageTaskMap.task_id.in_(task_ids)).delete(synchronize_session=False)
    if message_ids:
        db.query(MessageTaskMap).filter(MessageTaskMap.message_id.in_(message_ids)).delete(synchronize_session=False)
    db.query(Alert).filter(Alert.workspace_id == workspace_id).delete(synchronize_session=False)
    db.query(Task).filter(Task.workspace_id == workspace_id).delete(synchronize_session=False)
    db.query(Message).filter(Message.workspace_id == workspace_id).delete(synchronize_session=False)
    db.query(Channel).filter(Channel.workspace_id == workspace_id).delete(synchronize_session=False)
    db.query(WorkspaceMember).filter(WorkspaceMember.workspace_id == workspace_id).delete(synchronize_session=False)
    db.delete(workspace)
    db.commit()

    logger.info(f"Workspace '{ws_name}' (id={workspace_id}) deleted by user {user.id}")
    return {"ok": True, "message": f"Workspace '{ws_name}' deleted successfully"}
