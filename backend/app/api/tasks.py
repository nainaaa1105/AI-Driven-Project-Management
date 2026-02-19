"""
tasks.py — GET /tasks
======================
Returns all tasks with optional status filtering.
Also supports updating task status.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.task import TaskOut, TaskUpdatePayload
from app.models.custom_domain import CustomDomain
from app.services.task_service import (
    get_all_tasks,
    get_task_by_id,
    get_tasks_by_status,
    update_task_status,
    update_task_details,
    delete_task,
)

router = APIRouter(tags=["Tasks"])


# ── Custom Domains ──────────────────────────────────────────────────

@router.get("/domains", response_model=List[str])
def list_custom_domains(db: Session = Depends(get_db)):
    """Return all user-created custom domain names."""
    rows = db.query(CustomDomain).order_by(CustomDomain.name).all()
    return [r.name for r in rows]


@router.post("/domains")
def create_custom_domain(
    name: str = Query(..., min_length=1, max_length=100),
    db: Session = Depends(get_db),
):
    """Create a new custom domain (case-insensitive duplicate check)."""
    normalised = name.strip()
    exists = db.query(CustomDomain).filter(
        CustomDomain.name.ilike(normalised)
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail="Domain already exists")
    domain = CustomDomain(name=normalised)
    db.add(domain)
    db.commit()
    db.refresh(domain)
    return {"ok": True, "name": domain.name}


@router.get("/tasks", response_model=List[TaskOut])
def list_tasks(
    status: Optional[str] = Query(None, description="Filter by status: open, updated, resolved"),
    db: Session = Depends(get_db),
):
    """
    Return all tasks, optionally filtered by status.

    Used by the frontend Kanban board to display task cards.
    """
    if status:
        return get_tasks_by_status(db, status)
    return get_all_tasks(db)


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db)):
    """Return a single task by ID."""
    task = get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/tasks/{task_id}/status")
def patch_task_status(
    task_id: int,
    new_status: str = Query(..., description="New status value"),
    db: Session = Depends(get_db),
):
    """Update a task's status (e.g. open → in-progress → resolved)."""
    task = update_task_status(db, task_id, new_status)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True, "task_id": task.id, "status": task.status}


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def patch_task(
    task_id: int,
    payload: TaskUpdatePayload,
    db: Session = Depends(get_db),
):
    """
    User-driven task update: note, domains, urgency, status.
    After persisting, recalculates risk via ML-3 (non-destructive).
    """
    task = update_task_details(
        db, task_id,
        update_note=payload.update_note,
        domains=payload.domains,
        urgency=payload.urgency,
        status=payload.status,
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # ── Recalculate risk via ML-3 (lazy import to avoid circular) ────
    try:
        from app.services.ai_orchestrator import orchestrator
        if orchestrator._initialised:
            sentiment_score = 0.50
            text = (task.update_notes or task.description or task.title).lower()
            is_blocked = 1 if any(
                w in text for w in ["blocked", "stuck", "waiting", "blocker"]
            ) else 0
            has_dep = 1 if any(
                w in text for w in ["dependency", "depends", "waiting for", "need", "api"]
            ) else 0
            urg = task.urgency or "normal"
            risk_features = {
                "task_complexity": 0.7 if urg == "high" else 0.5,
                "dependency_count": min(has_dep * 0.6 + 0.1, 1.0),
                "sentiment_score": sentiment_score,
                "is_blocked": is_blocked,
                "idle_time_days": 30.0 if is_blocked else 10.0,
            }
            from risk_model import predict_risk as _predict_risk
            risk_out = _predict_risk(
                risk_features,
                orchestrator.risk_model,
                orchestrator.risk_scaler,
                orchestrator.risk_explainer,
            )
            task.risk_score = risk_out["risk_score"]
            task.risk_level = risk_out["risk_level"]
            task.risk_reason = risk_out["reason"]
            db.commit()
            db.refresh(task)
    except Exception:
        pass  # Risk recalc is best-effort; don't break the update

    return task


@router.delete("/tasks/{task_id}")
def remove_task(task_id: int, db: Session = Depends(get_db)):
    """Delete a task by ID."""
    deleted = delete_task(db, task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True, "task_id": task_id, "message": f"Task #{task_id} deleted"}
