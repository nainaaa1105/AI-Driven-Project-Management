"""
jwt_handler.py
==============
JWT token creation and verification using PyJWT.
"""

from datetime import datetime, timedelta
from typing import Optional

import jwt

from app.config import settings


def create_access_token(user_id: int, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token for the given user ID."""
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES))
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decode and verify a JWT token.

    Returns the payload dict on success.
    Raises jwt.ExpiredSignatureError or jwt.InvalidTokenError on failure.
    """
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
