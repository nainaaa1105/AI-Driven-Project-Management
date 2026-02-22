"""
dashboard.py — GET /dashboard
===============================
Aggregated statistics for the frontend dashboard.
Supports optional workspace scoping via query parameter.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.task import Task
from app.models.alert import Alert
from app.models.message import Message
from app.services.task_service import count_tasks_by_risk_level
from app.services.alert_service import count_alerts_by_level
from app.auth.dependencies import get_current_user, require_workspace_member

router = APIRouter(tags=["Dashboard"])


@router.get("/dashboard")
def get_dashboard(
    workspace_id: Optional[int] = Query(None, description="Scope dashboard to a workspace"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Return aggregated project intelligence data for the dashboard.

    If workspace_id is provided, results are scoped to that workspace
    and membership is verified.
    """
    if workspace_id:
        require_workspace_member(workspace_id, user, db)

    # Build filtered queries
    msg_query = db.query(Message)
    task_query = db.query(Task)
    alert_query = db.query(Alert)

    if workspace_id:
        msg_query = msg_query.filter(Message.workspace_id == workspace_id)
        task_query = task_query.filter(Task.workspace_id == workspace_id)
        alert_query = alert_query.filter(Alert.workspace_id == workspace_id)

    total_messages = msg_query.count()
    all_tasks = task_query.order_by(Task.created_at.desc()).all()
    all_alerts = alert_query.order_by(Alert.created_at.desc()).all()

    # Status breakdown
    status_counts: dict = {}
    for t in all_tasks:
        s = t.status or "open"
        status_counts[s] = status_counts.get(s, 0) + 1

    # Average risk
    risk_scores = [t.risk_score for t in all_tasks if t.risk_score is not None]
    avg_risk = round(sum(risk_scores) / len(risk_scores), 2) if risk_scores else 0.0

    # Recent items (serialised manually for speed)
    recent_tasks = [
        {
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "risk_score": t.risk_score,
            "risk_level": t.risk_level,
            "domain": t.domain,
            "urgency": t.urgency,
            "workspace_id": t.workspace_id,
            "assigned_user_id": t.assigned_user_id,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in all_tasks[:10]
    ]

    recent_alerts = [
        {
            "id": a.id,
            "message": a.message,
            "level": a.level,
            "task_id": a.task_id,
            "workspace_id": a.workspace_id,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in all_alerts[:10]
    ]

    return {
        "total_messages": total_messages,
        "total_tasks": len(all_tasks),
        "total_alerts": len(all_alerts),
        "tasks_by_risk": count_tasks_by_risk_level(db, workspace_id),
        "alerts_by_level": count_alerts_by_level(db, workspace_id),
        "tasks_by_status": status_counts,
        "recent_tasks": recent_tasks,
        "recent_alerts": recent_alerts,
        "avg_risk_score": avg_risk,
    }
