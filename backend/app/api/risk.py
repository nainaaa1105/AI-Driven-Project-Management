"""
risk.py — POST /risk/predict
==============================
Standalone risk prediction endpoint.
Accepts raw feature values and returns ML-3 output.
"""

from fastapi import APIRouter

from app.schemas.risk import RiskPredictRequest, RiskPredictResponse
from app.services.ai_orchestrator import orchestrator

router = APIRouter(tags=["Risk"])


@router.post("/risk/predict", response_model=RiskPredictResponse)
def predict_risk(payload: RiskPredictRequest):
    """
    Predict project failure risk from task features.

    Calls ML-3 (risk_model.predict_risk) directly with the supplied
    feature values.  Returns risk_score, risk_level, reason, and
    per-feature SHAP values.

    Input features (all 0-1 except idle_time_days):
      - task_complexity
      - dependency_count
      - sentiment_score
      - is_blocked (0 or 1)
      - idle_time_days (raw days)
    """
    features = payload.model_dump()
    result = orchestrator.predict_risk_standalone(features)
    return RiskPredictResponse(**result)
