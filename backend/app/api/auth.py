"""
auth.py — POST /auth/register, POST /auth/login
==================================================
Minimal JWT-based authentication system.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.hash import bcrypt

from app.database import get_db
from app.models.user import User
from app.auth.jwt_handler import create_access_token
from app.auth.dependencies import get_current_user
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger("api.auth")


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user account.

    Returns a JWT token on success.
    """
    # Check for existing user with same email
    existing = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = User(
        name=payload.name.strip(),
        email=payload.email.lower().strip(),
        password_hash=bcrypt.hash(payload.password),
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    logger.info(f"User registered: {user.email} (id={user.id})")

    return TokenResponse(
        access_token=token,
        user_id=user.id,
        name=user.name,
        email=user.email,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate with email and password.

    Returns a JWT token on success.
    """
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not bcrypt.verify(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(user.id)
    logger.info(f"User logged in: {user.email} (id={user.id})")

    return TokenResponse(
        access_token=token,
        user_id=user.id,
        name=user.name,
        email=user.email,
    )


@router.get("/me", response_model=UserOut)
def get_me(user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return user
