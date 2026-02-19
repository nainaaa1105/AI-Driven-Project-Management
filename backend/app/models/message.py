"""messages table – stores raw chat messages and AI analysis results."""

from sqlalchemy import Column, Integer, Text, DateTime, func

from app.database import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    content = Column(Text, nullable=False)
    sender = Column(Text, nullable=False, default="user")
    ai_response = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
