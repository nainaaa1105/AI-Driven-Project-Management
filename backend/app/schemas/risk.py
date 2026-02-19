"""Pydantic schemas for risk prediction endpoint."""

from typing import Optional, Dict
from pydantic import BaseModel, Field


class RiskPredictRequest(BaseModel):
    """Manual risk-prediction request from the frontend."""
    task_complexity: float = Field(0.5, ge=0.0, le=1.0)
    dependency_count: float = Field(0.3, ge=0.0, le=1.0)
    sentiment_score: float = Field(0.5, ge=0.0, le=1.0)
    is_blocked: int = Field(0, ge=0, le=1)
    idle_time_days: float = Field(30.0, ge=0.0)


class RiskPredictResponse(BaseModel):
    """Risk prediction result."""
    risk_score: float
    risk_level: str
    reason: str
    shap_values: Optional[Dict[str, float]] = None
