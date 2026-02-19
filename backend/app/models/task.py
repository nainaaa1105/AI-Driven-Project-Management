"""tasks table – engineered tasks extracted by the ML pipeline."""

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, func

from app.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True, default="")
    status = Column(String(50), nullable=False, default="open")
    risk_score = Column(Float, nullable=True, default=0.0)
    risk_level = Column(String(50), nullable=True, default="Low")
    risk_reason = Column(Text, nullable=True, default="")
    domain = Column(String(255), nullable=True, default="General")
    urgency = Column(String(50), nullable=True, default="normal")
    similarity_label = Column(String(50), nullable=True, default="NEW")
    linked_task_id = Column(Integer, nullable=True)
    update_notes = Column(Text, nullable=True, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
