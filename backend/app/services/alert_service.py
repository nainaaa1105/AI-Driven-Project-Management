"""
alert_service.py
================
CRUD helpers for the alerts table.
Supports workspace-scoped queries.
"""

from typing import List
from sqlalchemy.orm import Session

from app.models.alert import Alert


def get_all_alerts(db: Session, workspace_id: int = None) -> List[Alert]:
    """Return all alerts ordered by creation date (newest first)."""
    query = db.query(Alert)
    if workspace_id:
        query = query.filter(Alert.workspace_id == workspace_id)
    return query.order_by(Alert.created_at.desc()).all()


def get_alerts_for_task(db: Session, task_id: int) -> List[Alert]:
    """Return alerts associated with a specific task."""
    return (
        db.query(Alert)
        .filter(Alert.task_id == task_id)
        .order_by(Alert.created_at.desc())
        .all()
    )


def count_alerts_by_level(db: Session, workspace_id: int = None) -> dict:
    """Return a breakdown of alerts by severity level."""
    query = db.query(Alert)
    if workspace_id:
        query = query.filter(Alert.workspace_id == workspace_id)
    alerts = query.all()
    breakdown = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
    for a in alerts:
        level = a.level or "Medium"
        breakdown[level] = breakdown.get(level, 0) + 1
    return breakdown
