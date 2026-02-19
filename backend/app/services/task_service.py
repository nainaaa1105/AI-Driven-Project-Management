"""
task_service.py
===============
CRUD helpers for the tasks table.
Used by API endpoints to list, get, and update tasks.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.alert import Alert


def get_all_tasks(db: Session) -> List[Task]:
    """Return all tasks ordered by creation date (newest first)."""
    return db.query(Task).order_by(Task.created_at.desc()).all()


def get_task_by_id(db: Session, task_id: int) -> Optional[Task]:
    """Return a single task by primary key."""
    return db.query(Task).filter(Task.id == task_id).first()


def get_tasks_by_status(db: Session, status: str) -> List[Task]:
    """Return tasks filtered by status (open, updated, resolved …)."""
    return db.query(Task).filter(Task.status == status).order_by(Task.created_at.desc()).all()


def update_task_status(db: Session, task_id: int, new_status: str) -> Optional[Task]:
    """Set a new status on an existing task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        task.status = new_status
        db.commit()
        db.refresh(task)
    return task


def update_task_title(db: Session, task_id: int, new_title: str) -> Optional[Task]:
    """Update a task's title/description text."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        task.title = new_title
        db.commit()
        db.refresh(task)
    return task


def update_task_details(
    db: Session,
    task_id: int,
    update_note: Optional[str] = None,
    domains: Optional[list] = None,
    urgency: Optional[str] = None,
    status: Optional[str] = None,
) -> Optional[Task]:
    """Apply a user-driven partial update to a task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return None
    if update_note:
        from datetime import datetime
        stamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        entry = f"[{stamp}] {update_note}"
        task.update_notes = (task.update_notes or "") + ("\n" if task.update_notes else "") + entry
    if domains is not None:
        task.domain = ", ".join(domains)
    if urgency is not None:
        task.urgency = urgency
    if status is not None:
        task.status = status
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task_id: int) -> bool:
    """Delete a task by ID (and its linked alerts). Returns True if deleted, False if not found."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return False
    # Remove related alerts first to avoid FK constraint violation
    db.query(Alert).filter(Alert.task_id == task_id).delete()
    db.delete(task)
    db.commit()
    return True


def count_tasks_by_risk_level(db: Session) -> dict:
    """Return a breakdown of tasks by risk level for the dashboard."""
    tasks = db.query(Task).all()
    breakdown = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
    for t in tasks:
        level = t.risk_level or "Low"
        breakdown[level] = breakdown.get(level, 0) + 1
    return breakdown
