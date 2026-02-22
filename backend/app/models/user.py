"""users table – user identity with authentication support."""

from sqlalchemy import Column, Integer, String, DateTime, func

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True, unique=True, index=True)
    password_hash = Column(String(512), nullable=True)
    role = Column(String(50), nullable=False, default="user")  # user | system
    created_at = Column(DateTime(timezone=True), server_default=func.now())
