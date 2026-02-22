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

    # Create a temporary "ml" package whose __path__ is ml/ml_1_nlp/ml/
    fake_ml = types.ModuleType("ml")
    fake_ml.__path__ = [os.path.join(_ml1_dir, "ml")]
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

_ml3_dir = os.path.join(PROJECT_ROOT, "ml", "ml_3_risk_scoring")
if _ml3_dir not in sys.path:
    sys.path.insert(0, _ml3_dir)

from risk_model import (  # noqa: E402
    predict_risk as _predict_risk,
    build_golden_data,
    load_data as _load_risk_data,
    train as _train_risk,
    evaluate as _evaluate_risk,
    FEATURE_COLS,
    SCALE_COLS,
)

# ---------------------------------------------------------------------------
# DB model imports (deferred to avoid circular imports at module level)
# ---------------------------------------------------------------------------
from app.models.task import Task as DBTask
from app.models.alert import Alert as DBAlert
from app.models.message import Message as DBMessage
from app.models.message_task_map import MessageTaskMap
from app.models.ai_event import AIEvent


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
        model_dir = os.path.join(_ml3_dir, "model_artifacts")
        model_path = os.path.join(model_dir, "team_risk_model.pkl")
        scaler_path = os.path.join(model_dir, "team_feature_scaler.pkl")

        if os.path.exists(model_path) and os.path.exists(scaler_path):
            logger.info("  Found pre-trained artefacts — loading …")
            self.risk_model = joblib.load(model_path)
            self.risk_scaler = joblib.load(scaler_path)
        else:
            logger.info("  No pre-trained model found — training on golden data …")
            df = _load_risk_data()
            golden_df = build_golden_data()
            (
                self.risk_model,
                self.risk_scaler,
                _X_train, _y_train,
                _X_test, _y_test,
            ) = _train_risk(df, golden_df)
            # Persist for future runs
            os.makedirs(model_dir, exist_ok=True)
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
                workspace_id=str(t.workspace_id or ""),
            )
            for t in db_tasks
        ]
        self.similarity_engine.add_tasks(ml_tasks)

    # ==================================================================
    # MAIN PIPELINE — ML-1 → ML-2 → ML-3
    # ==================================================================
    def process_message(
        self,
        text: str,
        db: Session,
        workspace_id: int = None,
        channel_id: int = None,
        sender_id: int = None,
        message_id: int = None,
    ) -> dict:
        """
        End-to-end AI pipeline.

        Parameters
        ----------
        text         : str     – raw chat message from the user
        db           : Session – active SQLAlchemy session
        workspace_id : int     – workspace context (optional, for scoping)
        channel_id   : int     – channel context (optional)
        sender_id    : int     – user who sent the message (optional)
        message_id   : int     – DB id of the persisted message (optional)

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

        similar_results = self.similarity_engine.find_similar_tasks(
            task_name, workspace_id=str(workspace_id or ""),
        )
        decision = similar_results.get("decision", "create_new")
        top_match = (
            similar_results["similar_tasks"][0]
            if similar_results.get("similar_tasks")
            else None
        )
        # Map ML-2 decision vocabulary to the labels used below
        _decision_to_label = {
            "auto_link": "DUPLICATE",
            "suggest": "RELATED",
            "create_new": "NEW",
        }
        similarity_label = _decision_to_label.get(decision, "NEW")

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
                workspace_id=workspace_id,
                channel_id=channel_id,
                assigned_user_id=sender_id,
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
                workspace_id=workspace_id,
                channel_id=channel_id,
                assigned_user_id=sender_id,
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
                workspace_id=workspace_id,
            )
            db.add(alert)
            db.commit()
            logger.info(f"  ALERT created — {alert_msg}")

        # ──────────────────────────────────────────────────────────────
        # STEP 5b — Message → Task linkage
        # ──────────────────────────────────────────────────────────────
        if message_id and db_task:
            link = MessageTaskMap(
                message_id=message_id,
                task_id=db_task.id,
                relationship_type="spawned" if task_created else "linked",
            )
            db.add(link)
            db.commit()

        # ──────────────────────────────────────────────────────────────
        # STEP 5c — Log AI event
        # ──────────────────────────────────────────────────────────────
        event_type = "task_created" if task_created else "task_linked"
        if alert_msg:
            event_type = "risk_alert"
        ai_event = AIEvent(
            workspace_id=workspace_id,
            event_type=event_type,
            payload=json.dumps({
                "task_id": db_task.id if db_task else None,
                "similarity_label": similarity_label,
                "risk_score": risk_score,
                "risk_level": risk_level,
            }),
            triggered_by_message_id=message_id,
        )
        db.add(ai_event)
        db.commit()

        # ──────────────────────────────────────────────────────────────
        # STEP 5d — AI Bot message (announce in channel)
        # ──────────────────────────────────────────────────────────────
        if channel_id and db_task:
            self._post_ai_bot_message(db, workspace_id, channel_id, db_task, task_created, similarity_label, risk_level, risk_score, alert_msg)

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

    # ==================================================================
    # AI Bot message posting
    # ==================================================================
    def _post_ai_bot_message(
        self, db: Session,
        workspace_id: int, channel_id: int,
        db_task, task_created: bool,
        similarity_label: str, risk_level: str,
        risk_score: float, alert_msg: str = None,
    ):
        """
        Post an AI bot message into the channel announcing task actions.
        """
        from app.models.user import User
        from app.config import settings

        ai_bot = db.query(User).filter(User.email == settings.AI_BOT_EMAIL).first()
        if not ai_bot:
            return

        parts = []
        if task_created:
            parts.append(f"🤖 Task #{db_task.id} created: \"{db_task.title}\" [{similarity_label}]")
        else:
            parts.append(f"🤖 Task #{db_task.id} updated (duplicate detected)")

        parts.append(f"Risk: {risk_score:.0%} ({risk_level})")

        if alert_msg:
            parts.append(alert_msg)

        bot_content = " | ".join(parts)

        bot_msg = DBMessage(
            content=bot_content,
            sender=ai_bot.name,
            sender_id=ai_bot.id,
            workspace_id=workspace_id,
            channel_id=channel_id,
        )
        db.add(bot_msg)
        db.commit()
        logger.info(f"  AI Bot posted message in channel {channel_id}")

    # ==================================================================
    # Risk queries for GET endpoints
    # ==================================================================
    def get_task_risk(self, db: Session, task_id: int) -> dict:
        """Get risk information for a specific task."""
        task = db.query(DBTask).filter(DBTask.id == task_id).first()
        if not task:
            return None
        return {
            "task_id": task.id,
            "risk_score": task.risk_score or 0.0,
            "risk_level": task.risk_level or "Low",
            "explanation": task.risk_reason or "No risk data available",
        }

    def get_workspace_risk(self, db: Session, workspace_id: int) -> dict:
        """Aggregate risk information for all tasks in a workspace."""
        tasks = db.query(DBTask).filter(DBTask.workspace_id == workspace_id).all()
        if not tasks:
            return {
                "workspace_id": workspace_id,
                "total_tasks": 0,
                "avg_risk_score": 0.0,
                "risk_level": "Low",
                "explanation": "No tasks in this workspace",
                "risk_distribution": {"Low": 0, "Medium": 0, "High": 0, "Critical": 0},
                "high_risk_tasks": [],
            }

        risk_scores = [t.risk_score for t in tasks if t.risk_score is not None]
        avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0.0

        distribution = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
        for t in tasks:
            level = t.risk_level or "Low"
            distribution[level] = distribution.get(level, 0) + 1

        # Overall risk level
        if avg_risk > 0.7:
            overall_level = "Critical" if avg_risk > 0.85 else "High"
        elif avg_risk > 0.4:
            overall_level = "Medium"
        else:
            overall_level = "Low"

        high_risk_tasks = [
            {"task_id": t.id, "title": t.title, "risk_score": t.risk_score, "risk_level": t.risk_level}
            for t in tasks if t.risk_score and t.risk_score > 0.7
        ]

        return {
            "workspace_id": workspace_id,
            "total_tasks": len(tasks),
            "avg_risk_score": round(avg_risk, 4),
            "risk_level": overall_level,
            "explanation": f"{len(high_risk_tasks)} high-risk tasks out of {len(tasks)} total",
            "risk_distribution": distribution,
            "high_risk_tasks": high_risk_tasks,
        }


# Module-level singleton accessor
orchestrator = AIOrchestrator()
