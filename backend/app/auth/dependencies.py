"""
dependencies.py
===============
FastAPI dependencies for authentication and workspace authorization.
"""

from typing import List

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.jwt_handler import decode_access_token
from app.models.user import User
from app.models.workspace_member import WorkspaceMember

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Extract and validate the current user from the JWT bearer token.
    Attaches the user ORM object to the request context.
    """
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def require_workspace_member(
    workspace_id: int,
    user: User,
    db: Session,
) -> WorkspaceMember:
    """
    Verify the user is a member of the specified workspace.
    Returns the WorkspaceMember record.
    Raises 403 if user is not a member.
    """
    member = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id,
        )
        .first()
    )
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this workspace",
        )
    return member


def require_workspace_role(
    workspace_id: int,
    user: User,
    db: Session,
    roles: List[str],
) -> WorkspaceMember:
    """
    Verify the user has one of the required roles in the workspace.
    Returns the WorkspaceMember record.
    Raises 403 if the user lacks the required role.
    """
    member = require_workspace_member(workspace_id, user, db)
    if member.role not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Required: {', '.join(roles)}",
        )
    return member
