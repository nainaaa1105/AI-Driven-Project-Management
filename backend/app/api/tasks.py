"""
tasks.py — Task CRUD APIs
===========================
Returns all tasks with optional status and workspace filtering.
Supports updating task status, details, and assignment.
All endpoints require authentication.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.task import Task
from app.schemas.task import TaskOut, TaskUpdatePayload
from app.models.custom_domain import CustomDomain
from app.auth.dependencies import get_current_user, require_workspace_member
from app.services.task_service import (
    get_all_tasks,
    get_task_by_id,
    get_tasks_by_status,
    get_tasks_by_workspace,
    update_task_status,
    update_task_details,
    delete_task,
)

router = APIRouter(tags=["Tasks"])


# ── Custom Domains ──────────────────────────────────────────────────

@router.get("/domains", response_model=List[str])
def list_custom_domains(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return all user-created custom domain names."""
    rows = db.query(CustomDomain).order_by(CustomDomain.name).all()
    return [r.name for r in rows]


@router.post("/domains")
def create_custom_domain(
    name: str = Query(..., min_length=1, max_length=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
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
    workspace_id: Optional[int] = Query(None, description="Filter by workspace"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Return tasks, optionally filtered by status and/or workspace.
    If workspace_id is provided, verifies membership first.
    """
    if workspace_id:
        require_workspace_member(workspace_id, user, db)
        return get_tasks_by_workspace(db, workspace_id, status)
    if status:
        return get_tasks_by_status(db, status)
    return get_all_tasks(db)


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
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
    user: User = Depends(get_current_user),
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
    user: User = Depends(get_current_user),
):
    """
    User-driven task update: note, domains, urgency, status, assignment.
    After persisting, recalculates risk via ML-3 (non-destructive).
    """
    task = update_task_details(
        db, task_id,
        update_note=payload.update_note,
        domains=payload.domains,
        urgency=payload.urgency,
        status=payload.status,
        assigned_user_id=payload.assigned_user_id,
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
            risk_out = orchestrator.predict_risk_standalone(risk_features)
            task.risk_score = risk_out["risk_score"]
            task.risk_level = risk_out["risk_level"]
            task.risk_reason = risk_out["reason"]
            db.commit()
            db.refresh(task)
    except Exception:
        pass  # Risk recalc is best-effort; don't break the update

    return task


@router.delete("/tasks/{task_id}")
def remove_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a task by ID."""
    deleted = delete_task(db, task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True, "task_id": task_id, "message": f"Task #{task_id} deleted"}
