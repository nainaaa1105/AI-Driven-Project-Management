"""ai_events table – audit log of all AI-driven actions."""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func

from app.database import Base


class AIEvent(Base):
    __tablename__ = "ai_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(100), nullable=False)  # task_created | task_linked | risk_alert | suggestion
    payload = Column(Text, nullable=True)  # JSON-encoded details
    triggered_by_message_id = Column(Integer, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
