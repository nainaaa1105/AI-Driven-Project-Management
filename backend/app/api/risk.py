"""
risk.py — Risk prediction and query endpoints
================================================
POST /risk/predict    — Standalone risk prediction from raw features
GET  /risk/task/{id}  — Risk info for a specific task
GET  /risk/workspace/{id} — Aggregated risk for a workspace
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.risk import RiskPredictRequest, RiskPredictResponse
from app.services.ai_orchestrator import orchestrator
from app.auth.dependencies import get_current_user, require_workspace_member

router = APIRouter(tags=["Risk"])


@router.post("/risk/predict", response_model=RiskPredictResponse)
def predict_risk(
    payload: RiskPredictRequest,
    user: User = Depends(get_current_user),
):
    """
    Predict project failure risk from task features.

    Calls ML-3 (risk_model.predict_risk) directly with the supplied
    feature values.  Returns risk_score, risk_level, reason, and
    per-feature SHAP values.
    """
    features = payload.model_dump()
    result = orchestrator.predict_risk_standalone(features)
    return RiskPredictResponse(**result)


@router.get("/risk/task/{task_id}")
def get_task_risk(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Return risk information for a specific task.

    Response: { task_id, risk_score, risk_level, explanation }
    """
    result = orchestrator.get_task_risk(db, task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@router.get("/risk/workspace/{workspace_id}")
def get_workspace_risk(
    workspace_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Return aggregated risk information for a workspace.

    Response: { workspace_id, total_tasks, avg_risk_score, risk_level,
                explanation, risk_distribution, high_risk_tasks }
    """
    require_workspace_member(workspace_id, user, db)
    return orchestrator.get_workspace_risk(db, workspace_id)
