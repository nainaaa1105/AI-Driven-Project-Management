"""
ai_orchestrator.py
==================
Central AI pipeline that chains the three ML modules:

  ML-1 (NLP)   → classify message, extract entities, generate executive report
  ML-2 (Task)  → find similar/duplicate tasks via hybrid TF-IDF + semantic search
  ML-3 (Risk)  → predict project failure risk with SHAP explanations

Data flow
---------
  raw chat message  ──►  ML-1  ──►  executive_report (summary, urgency, domain …)
                                     │
                         task_name ◄─┘
                            │
                            ▼
                          ML-2  ──►  DUPLICATE / RELATED / NEW  ──►  DB upsert
                                     │
                         features ◄──┘
                            │
                            ▼
                          ML-3  ──►  risk_score, risk_level, reason
                                     │
                           alert  ◄──┘  (if risk_score > 0.7)
"""

import os
import sys
import types
import json
import logging
import traceback

import numpy as np
import joblib

from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Project root — two levels up from  backend/app/services/
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, os.pardir)
)

logger = logging.getLogger("ai_orchestrator")

# ═══════════════════════════════════════════════════════════════════════════════
# ML-1 — NLP processor (MessageClassifier + EntityExtractor)
# ═══════════════════════════════════════════════════════════════════════════════
#
# ml_demo.py internally does:
#     from ml.nlp_classifier  import MessageClassifier
#     from ml.entity_extractor import EntityExtractor
#
# This expects a package named "ml" that contains nlp_classifier.py.
# The actual files live at  ml/ml_1_nlp/nlp_classifier.py.
# We temporarily redirect the "ml" entry in sys.modules so the import resolves.
# ---------------------------------------------------------------------------

_ml1_dir = os.path.join(PROJECT_ROOT, "ml", "ml_1_nlp")


def _load_ml_processor():
    """
    Dynamically load MLProcessor from ml/ml_1_nlp/ml_demo.py
    by temporarily patching sys.modules['ml'] to point at the ml_1_nlp dir.
    """
    # Save any existing 'ml' module entries
    saved = {}
    for key in list(sys.modules.keys()):
        if key == "ml" or key.startswith("ml."):
            saved[key] = sys.modules.pop(key)

    # Create a temporary "ml" package whose __path__ is ml/ml_1_nlp/
    fake_ml = types.ModuleType("ml")
    fake_ml.__path__ = [_ml1_dir]
    fake_ml.__package__ = "ml"
    sys.modules["ml"] = fake_ml

    if _ml1_dir not in sys.path:
        sys.path.insert(0, _ml1_dir)

    # This triggers ml_demo.py  →  from ml.nlp_classifier import ...  → OK
    from ml_demo import MLProcessor  # noqa: E402

    # Restore original 'ml' module entries
    for key in list(sys.modules.keys()):
        if key == "ml" or key.startswith("ml."):
            sys.modules.pop(key, None)
    sys.modules.update(saved)

    return MLProcessor


# ═══════════════════════════════════════════════════════════════════════════════
# ML-2 — Task Similarity Engine
# ═══════════════════════════════════════════════════════════════════════════════
#
# task_similarity.py does  `from thresholds import …`  (sibling import).
# We add ml/ml_2_task/ to sys.path so "thresholds" is discoverable.
# ---------------------------------------------------------------------------

_ml2_dir = os.path.join(PROJECT_ROOT, "ml", "ml_2_task")
if _ml2_dir not in sys.path:
    sys.path.insert(0, _ml2_dir)

from task_similarity import TaskSimilarityEngine, Task as MLTask  # noqa: E402

# ═══════════════════════════════════════════════════════════════════════════════
# ML-3 — Risk prediction
# ═══════════════════════════════════════════════════════════════════════════════

_ml3_dir = os.path.join(PROJECT_ROOT, "ml", "ml_3_risk")
if _ml3_dir not in sys.path:
    sys.path.insert(0, _ml3_dir)

from risk_model import (  # noqa: E402
    predict_risk as _predict_risk,
    build_golden_data,
    train_model,
    FEATURE_COLS,
    SCALE_COLS,
)

# ---------------------------------------------------------------------------
# DB model imports (deferred to avoid circular imports at module level)
# ---------------------------------------------------------------------------
from app.models.task import Task as DBTask
from app.models.alert import Alert as DBAlert
from app.models.message import Message as DBMessage


# ═══════════════════════════════════════════════════════════════════════════════
# Orchestrator singleton
# ═══════════════════════════════════════════════════════════════════════════════


class AIOrchestrator:
    """
    Singleton that holds heavy ML models in memory and exposes
    ``process_message(text, db)`` as the single entry-point.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialised = False
        return cls._instance

    # ------------------------------------------------------------------
    def initialise(self) -> None:
        """Load all three ML modules (call once at startup)."""
        if self._initialised:
            return

        logger.info("Loading ML-1 (NLP processor) …")
        MLProcessorClass = _load_ml_processor()
        self.nlp = MLProcessorClass()

        logger.info("Loading ML-2 (Task Similarity Engine) …")
        self.similarity_engine = TaskSimilarityEngine()

        logger.info("Loading ML-3 (Risk model) …")
        self._load_risk_model()

        self._initialised = True
        logger.info("AI Orchestrator ready.")

    # ------------------------------------------------------------------
    def _load_risk_model(self) -> None:
        """
        Load pre-trained risk model artefacts (risk_model.pkl, feature_scaler.pkl).
        If they don't exist, train on golden scenarios and export.
        """
        model_path = os.path.join(_ml3_dir, "risk_model.pkl")
        scaler_path = os.path.join(_ml3_dir, "feature_scaler.pkl")

        if os.path.exists(model_path) and os.path.exists(scaler_path):
            logger.info("  Found pre-trained artefacts — loading …")
            self.risk_model = joblib.load(model_path)
            self.risk_scaler = joblib.load(scaler_path)
        else:
            logger.info("  No pre-trained model found — training on golden data …")
            golden_df = build_golden_data()
            weights = np.ones(len(golden_df))
            (
                self.risk_model,
                self.risk_scaler,
                _X_train, _y_train,
                _X_test, _y_test,
                _shap_vals, _shap_sample,
                _explainer, _mean_shap,
            ) = train_model(golden_df, weights)
            # Persist for future runs
            joblib.dump(self.risk_model, model_path)
            joblib.dump(self.risk_scaler, scaler_path)
            logger.info("  Model trained and saved.")

        # Build SHAP explainer from the loaded model
        import shap
        self.risk_explainer = shap.TreeExplainer(self.risk_model)

    # ------------------------------------------------------------------
    # Index existing DB tasks into ML-2
    # ------------------------------------------------------------------
    def _sync_task_index(self, db: Session) -> None:
        """
        Pull all tasks from the DB and feed them into the similarity engine
        so it can detect duplicates / related items.
        """
        db_tasks = db.query(DBTask).all()
        ml_tasks = [
            MLTask(
                id=t.id,
                title=t.title,
                description=t.description or "",
                past_outcome="success" if t.risk_score and t.risk_score < 0.5 else "delayed",
            )
            for t in db_tasks
        ]
        self.similarity_engine.add_tasks(ml_tasks)

    # ==================================================================
    # MAIN PIPELINE — ML-1 → ML-2 → ML-3
    # ==================================================================
    def process_message(self, text: str, db: Session) -> dict:
        """
        End-to-end AI pipeline.

        Parameters
        ----------
        text : str   – raw chat message from the user
        db   : Session – active SQLAlchemy session

        Returns
        -------
        dict with keys:
            summary, task_created, task_id, similarity_label,
            risk_score, risk_level, risk_reason, alert,
            domain, urgency, executive_report
        """
        if not self._initialised:
            self.initialise()

        # ──────────────────────────────────────────────────────────────
        # STEP 1 — ML-1: NLP classification & entity extraction
        # ──────────────────────────────────────────────────────────────
        logger.info("[ML-1] Processing message …")
        ml1_output = self.nlp.process_message(text)
        executive_report = ml1_output.get("executive_report", {})
        tech_details = ml1_output.get("technical_details", {})

        summary = executive_report.get("summary", "General update")
        urgency = executive_report.get("urgency", "normal")
        domain = executive_report.get("domain", "General")
        status = executive_report.get("status", "Pending/Active")
        sentiment = tech_details.get("sentiment", "neutral")

        task_name = summary if summary != "General update/discussion" else text[:120]

        # ──────────────────────────────────────────────────────────────
        # STEP 2 — ML-2: Duplicate / Related / New detection
        # ──────────────────────────────────────────────────────────────
        logger.info("[ML-2] Checking task similarity …")
        self._sync_task_index(db)

        similar_results = self.similarity_engine.find_similar_tasks(task_name)
        top_match = similar_results[0] if similar_results else None
        similarity_label = top_match["label"] if top_match else "NEW"

        # ──────────────────────────────────────────────────────────────
        # STEP 3 — Create / update / link task in DB
        # ──────────────────────────────────────────────────────────────
        task_created = False
        linked_task_id = None
        db_task = None

        if similarity_label == "DUPLICATE" and top_match:
            # Update existing task instead of creating a duplicate
            db_task = db.query(DBTask).filter(DBTask.id == top_match["task_id"]).first()
            if db_task:
                db_task.status = "updated"
                db_task.urgency = urgency
                db.commit()
                db.refresh(db_task)
                logger.info(f"  DUPLICATE — updated task #{db_task.id}")

        elif similarity_label == "RELATED" and top_match:
            linked_task_id = top_match["task_id"]
            db_task = DBTask(
                title=task_name,
                description=text[:500],
                status="open",
                domain=domain,
                urgency=urgency,
                similarity_label="RELATED",
                linked_task_id=linked_task_id,
            )
            db.add(db_task)
            db.commit()
            db.refresh(db_task)
            task_created = True
            logger.info(f"  RELATED — created task #{db_task.id} linked to #{linked_task_id}")

        else:
            # NEW task
            db_task = DBTask(
                title=task_name,
                description=text[:500],
                status="open",
                domain=domain,
                urgency=urgency,
                similarity_label="NEW",
            )
            db.add(db_task)
            db.commit()
            db.refresh(db_task)
            task_created = True
            logger.info(f"  NEW — created task #{db_task.id}")

        # ──────────────────────────────────────────────────────────────
        # STEP 4 — ML-3: Risk prediction
        # ──────────────────────────────────────────────────────────────
        logger.info("[ML-3] Predicting risk …")

        # Map NLP outputs to risk model features
        sentiment_map = {"positive": 0.85, "neutral": 0.50, "negative": 0.15}
        sentiment_score = sentiment_map.get(sentiment, 0.50)
        is_blocked = 1 if any(
            w in text.lower() for w in ["blocked", "stuck", "waiting", "blocker", "can't", "cannot"]
        ) else 0
        intents = tech_details.get("intents", [])
        has_dependency = 1 if any(
            w in text.lower() for w in ["dependency", "depends", "waiting for", "need", "api"]
        ) else 0
        task_complexity = 0.7 if urgency == "high" else 0.5

        risk_features = {
            "task_complexity": task_complexity,
            "dependency_count": min(has_dependency * 0.6 + 0.1, 1.0),
            "sentiment_score": sentiment_score,
            "is_blocked": is_blocked,
            "idle_time_days": 30.0 if is_blocked else 10.0,
        }

        risk_output = _predict_risk(
            risk_features, self.risk_model, self.risk_scaler, self.risk_explainer
        )
        risk_score = risk_output["risk_score"]
        risk_level = risk_output["risk_level"]
        risk_reason = risk_output["reason"]

        # Write risk back to the task row
        if db_task:
            db_task.risk_score = risk_score
            db_task.risk_level = risk_level
            db_task.risk_reason = risk_reason
            db.commit()

        # ──────────────────────────────────────────────────────────────
        # STEP 5 — Alert generation (risk_score > 0.7)
        # ──────────────────────────────────────────────────────────────
        alert_msg = None
        if risk_score > 0.7:
            alert_msg = f"⚠ High risk ({risk_level}): {risk_reason}"
            alert = DBAlert(
                message=alert_msg,
                level=risk_level,
                task_id=db_task.id if db_task else None,
            )
            db.add(alert)
            db.commit()
            logger.info(f"  ALERT created — {alert_msg}")

        # ──────────────────────────────────────────────────────────────
        # STEP 6 — Compose result
        # ──────────────────────────────────────────────────────────────
        result = {
            "summary": summary,
            "task_created": task_created,
            "task_id": db_task.id if db_task else None,
            "similarity_label": similarity_label,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_reason": risk_reason,
            "alert": alert_msg,
            "domain": domain,
            "urgency": urgency,
            "executive_report": executive_report,
        }
        logger.info(f"Pipeline complete → {json.dumps({k: v for k, v in result.items() if k != 'executive_report'})}")
        return result

    # ==================================================================
    # Standalone risk prediction (for POST /risk/predict)
    # ==================================================================
    def predict_risk_standalone(self, features: dict) -> dict:
        """
        Directly call ML-3 with user-supplied feature values.

        Parameters
        ----------
        features : dict with task_complexity, dependency_count,
                   sentiment_score, is_blocked, idle_time_days

        Returns
        -------
        dict  { risk_score, risk_level, reason, shap_values }
        """
        if not self._initialised:
            self.initialise()
        return _predict_risk(
            features, self.risk_model, self.risk_scaler, self.risk_explainer
        )


# Module-level singleton accessor
orchestrator = AIOrchestrator()
