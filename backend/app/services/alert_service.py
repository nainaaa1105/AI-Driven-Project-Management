"""
alert_service.py
================
CRUD helpers for the alerts table.
"""

from typing import List
from sqlalchemy.orm import Session

from app.models.alert import Alert


def get_all_alerts(db: Session) -> List[Alert]:
    """Return all alerts ordered by creation date (newest first)."""
    return db.query(Alert).order_by(Alert.created_at.desc()).all()


def get_alerts_for_task(db: Session, task_id: int) -> List[Alert]:
    """Return alerts associated with a specific task."""
    return (
        db.query(Alert)
        .filter(Alert.task_id == task_id)
        .order_by(Alert.created_at.desc())
        .all()
    )


def count_alerts_by_level(db: Session) -> dict:
    """Return a breakdown of alerts by severity level."""
    alerts = db.query(Alert).all()
    breakdown = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
    for a in alerts:
        level = a.level or "Medium"
        breakdown[level] = breakdown.get(level, 0) + 1
    return breakdown
