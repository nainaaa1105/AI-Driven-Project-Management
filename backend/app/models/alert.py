"""alerts table – risk-triggered alerts linked to tasks."""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func

from app.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    message = Column(Text, nullable=False)
    level = Column(String(50), nullable=False, default="Medium")
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
