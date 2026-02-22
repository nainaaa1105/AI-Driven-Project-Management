"""message_task_map table – links messages to tasks they spawned or reference."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func

from app.database import Base


class MessageTaskMap(Base):
    __tablename__ = "message_task_map"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    relationship_type = Column(String(50), nullable=False, default="spawned")  # spawned | linked | mentioned
    created_at = Column(DateTime(timezone=True), server_default=func.now())
