"""
dashboard.py — GET /dashboard
===============================
Aggregated statistics for the frontend dashboard.
"""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task
from app.models.alert import Alert
from app.models.message import Message
from app.services.task_service import count_tasks_by_risk_level
from app.services.alert_service import count_alerts_by_level

router = APIRouter(tags=["Dashboard"])


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    """
    Return aggregated project intelligence data for the dashboard.

    Response shape:
    {
      "total_messages": int,
      "total_tasks": int,
      "total_alerts": int,
      "tasks_by_risk": { "Low": n, "Medium": n, "High": n, "Critical": n },
      "alerts_by_level": { "Low": n, "Medium": n, "High": n, "Critical": n },
      "tasks_by_status": { "open": n, "updated": n, ... },
      "recent_tasks": [ ... top 10 ... ],
      "recent_alerts": [ ... top 10 ... ],
      "avg_risk_score": float
    }
    """
    total_messages = db.query(Message).count()
    all_tasks = db.query(Task).order_by(Task.created_at.desc()).all()
    all_alerts = db.query(Alert).order_by(Alert.created_at.desc()).all()

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
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in all_alerts[:10]
    ]

    return {
        "total_messages": total_messages,
        "total_tasks": len(all_tasks),
        "total_alerts": len(all_alerts),
        "tasks_by_risk": count_tasks_by_risk_level(db),
        "alerts_by_level": count_alerts_by_level(db),
        "tasks_by_status": status_counts,
        "recent_tasks": recent_tasks,
        "recent_alerts": recent_alerts,
        "avg_risk_score": avg_risk,
    }
