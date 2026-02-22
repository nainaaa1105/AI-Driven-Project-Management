"""Pydantic schemas for authentication."""

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """User registration payload."""
    name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    """User login payload."""
    email: str
    password: str


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    user_id: int
    name: str
    email: str


class UserOut(BaseModel):
    """Public user information."""
    id: int
    name: str
    email: str | None = None
    role: str = "user"

    class Config:
        from_attributes = True
