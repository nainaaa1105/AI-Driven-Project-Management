"""Custom domains table — user-created domain labels persisted globally."""

from sqlalchemy import Column, Integer, String, DateTime, func

from app.database import Base


class CustomDomain(Base):
    __tablename__ = "custom_domains"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
