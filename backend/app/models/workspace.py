"""workspaces table – collaborative workspace containers."""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func

from app.database import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True, default="")
    access_type = Column(String(20), nullable=False, default="private")  # private | open
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
