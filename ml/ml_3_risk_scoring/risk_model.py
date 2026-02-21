"""
risk_model.py  (ml_3_risk_scoring — Multi-User Team Edition)
=============================================================
Trains a RandomForestRegressor on Discord-style team interaction data
and provides a SHAP-explainable predict_risk() deployment API.

Differences from ml_3_risk (single-user):
  • Features are team-communication signals (response time, mentions, etc.)
  • Handles workspace-level data from generate_team_data.py
  • Golden data covers critical Discord alert patterns
  • SHAP reasons mapped to team-specific language
  • Model saved to ./model_artifacts/ (relative path)

Pipeline
--------
Step 1 – Load synthetic team data (or generate if missing)
Step 2 – Feature engineering + Golden data injection
Step 3 – GridSearchCV (3-fold, pruned params) → RandomForestRegressor
Step 4 – SHAP explainability + evaluation metrics
Step 5 – Export model_artifacts/ + predict_risk() demo
"""

import json
import os
import sys
import warnings

import joblib
import matplotlib
import matplotlib.pyplot as plt
import numpy  as np
import pandas as pd
import seaborn as sns
import shap

from sklearn.ensemble        import RandomForestRegressor
from sklearn.metrics         import mean_absolute_error, r2_score
from sklearn.model_selection import GridSearchCV, KFold, learning_curve, train_test_split
from sklearn.preprocessing   import MinMaxScaler

warnings.filterwarnings("ignore")
matplotlib.use("Agg")
np.random.seed(42)

# ─── Paths (all relative to this file's location) ────────────────────────────
_HERE         = os.path.dirname(os.path.abspath(__file__))
DATA_PATH     = os.path.join(_HERE, "synthetic_data", "team_task_data.csv")
ARTIFACTS_DIR = os.path.join(_HERE, "model_artifacts")
MODEL_PATH    = os.path.join(ARTIFACTS_DIR, "team_risk_model.pkl")
SCALER_PATH   = os.path.join(ARTIFACTS_DIR, "team_feature_scaler.pkl")
PLOTS_DIR     = os.path.join(_HERE, "plots")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)
os.makedirs(PLOTS_DIR,     exist_ok=True)

# ─── Feature definitions ──────────────────────────────────────────────────────
BASE_FEATURES = [
    "avg_response_time_hrs",      # raw hours — will be log-transformed
    "unanswered_mentions",        # count — will be log-transformed
    "dependency_chain_length",    # integer 1-8
    "task_owner_workload_score",  # 0-1 float
    "is_blocked",                 # 0/1 binary
]
INTERACTION_FEATURES = [
    "log_response_time",          # log1p(avg_response_time_hrs)
    "log_mentions",               # log1p(unanswered_mentions)
    "blocked_x_workload",         # is_blocked × workload_score
    "mention_x_response",         # unanswered_mentions × resp_norm
    "dep_x_workload",             # dependency_chain × workload
]
FEATURE_COLS = BASE_FEATURES + INTERACTION_FEATURES   # 10 features
TARGET_COL   = "risk_score"
# Columns that need MinMaxScaling (not already in [0,1])
SCALE_COLS   = [
    "avg_response_time_hrs", "unanswered_mentions",
    "dependency_chain_length", "log_response_time",
    "log_mentions", "mention_x_response", "dep_x_workload",
]

REASON_TEMPLATES = {
    "log_response_time"    : "Team member has been unresponsive for an unusually long period.",
    "avg_response_time_hrs": "High average response time signals communication breakdown.",
    "log_mentions"         : "Multiple unanswered @mentions — critical coordination failure.",
    "unanswered_mentions"  : "Team member is being consistently ignored in channels.",
    "blocked_x_workload"   : "Blocked task owned by an already overloaded user — cascade risk.",
    "mention_x_response"   : "Slow responses combined with ignored mentions — disengaged owner.",
    "dep_x_workload"       : "Long dependency chain owned by overloaded user amplifies delays.",
    "dependency_chain_length": "Long dependency chain creates cascading failure risk.",
    "task_owner_workload_score": "Task owner is critically overloaded.",
    "is_blocked"           : "Task is actively blocked with no current resolution path.",
}

RISK_BANDS = [(0.85, "Critical"), (0.65, "High"), (0.40, "Medium"), (0.00, "Low")]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _resolve_level(score: float) -> str:
    for threshold, label in RISK_BANDS:
        if score >= threshold:
            return label
    return "Low"


def _add_interaction_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all interaction features in-place. Works on both train and inference."""
    df = df.copy()
    resp_norm = (df["avg_response_time_hrs"] / 72.0).clip(0, 1)

    df["log_response_time"] = np.log1p(df["avg_response_time_hrs"])
    df["log_mentions"]      = np.log1p(df["unanswered_mentions"])
    df["blocked_x_workload"]= df["is_blocked"].astype(float) * df["task_owner_workload_score"]
    df["mention_x_response"]= df["unanswered_mentions"] * resp_norm
    df["dep_x_workload"]    = df["dependency_chain_length"] * df["task_owner_workload_score"]

    # NaN / Inf guard
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df.fillna(df.median(numeric_only=True), inplace=True)
    return df


# ─── Step 1: Data loading ─────────────────────────────────────────────────────

def load_data() -> pd.DataFrame:
    if not os.path.exists(DATA_PATH):
        print("  team_task_data.csv not found — generating now …")
        sys.path.insert(0, _HERE)
        from synthetic_data.generate_team_data import generate
        df = generate(2000)
        df.to_csv(DATA_PATH, index=False)
        print(f"  Generated + saved: {DATA_PATH}")
    else:
        df = pd.read_csv(DATA_PATH)

    print(f"  Loaded data: {df.shape[0]:,} rows × {df.shape[1]} cols")
    return df


# ─── Step 2: Golden data (critical Discord alert patterns) ────────────────────

def build_golden_data() -> pd.DataFrame:
    """
    15 hand-crafted golden scenarios covering every critical team pattern.
    Repeated 40× and injected into training with 3× sample weight.
    """
    base = [
        # CRITICAL: slow response + ignored mentions
        {"avg_response_time_hrs": 68, "unanswered_mentions": 9,
         "dependency_chain_length": 7, "task_owner_workload_score": 0.95,
         "is_blocked": 1, "risk_score": 0.98},
        {"avg_response_time_hrs": 55, "unanswered_mentions": 8,
         "dependency_chain_length": 6, "task_owner_workload_score": 0.90,
         "is_blocked": 1, "risk_score": 0.96},
        {"avg_response_time_hrs": 48, "unanswered_mentions": 7,
         "dependency_chain_length": 5, "task_owner_workload_score": 0.88,
         "is_blocked": 1, "risk_score": 0.94},
        # HIGH: slow response, no block
        {"avg_response_time_hrs": 36, "unanswered_mentions": 5,
         "dependency_chain_length": 4, "task_owner_workload_score": 0.75,
         "is_blocked": 0, "risk_score": 0.82},
        {"avg_response_time_hrs": 30, "unanswered_mentions": 4,
         "dependency_chain_length": 5, "task_owner_workload_score": 0.70,
         "is_blocked": 0, "risk_score": 0.78},
        # HIGH: blocked + overloaded
        {"avg_response_time_hrs": 20, "unanswered_mentions": 2,
         "dependency_chain_length": 6, "task_owner_workload_score": 0.92,
         "is_blocked": 1, "risk_score": 0.85},
        # MEDIUM: moderate signals
        {"avg_response_time_hrs": 12, "unanswered_mentions": 2,
         "dependency_chain_length": 3, "task_owner_workload_score": 0.50,
         "is_blocked": 0, "risk_score": 0.50},
        {"avg_response_time_hrs": 15, "unanswered_mentions": 3,
         "dependency_chain_length": 4, "task_owner_workload_score": 0.55,
         "is_blocked": 0, "risk_score": 0.53},
        {"avg_response_time_hrs": 10, "unanswered_mentions": 3,
         "dependency_chain_length": 3, "task_owner_workload_score": 0.45,
         "is_blocked": 1, "risk_score": 0.58},
        # MEDIUM-LOW
        {"avg_response_time_hrs": 6, "unanswered_mentions": 1,
         "dependency_chain_length": 2, "task_owner_workload_score": 0.35,
         "is_blocked": 0, "risk_score": 0.30},
        # LOW: healthy team
        {"avg_response_time_hrs": 1, "unanswered_mentions": 0,
         "dependency_chain_length": 1, "task_owner_workload_score": 0.10,
         "is_blocked": 0, "risk_score": 0.05},
        {"avg_response_time_hrs": 2, "unanswered_mentions": 0,
         "dependency_chain_length": 1, "task_owner_workload_score": 0.15,
         "is_blocked": 0, "risk_score": 0.08},
        {"avg_response_time_hrs": 3, "unanswered_mentions": 0,
         "dependency_chain_length": 2, "task_owner_workload_score": 0.20,
         "is_blocked": 0, "risk_score": 0.12},
        {"avg_response_time_hrs": 4, "unanswered_mentions": 1,
         "dependency_chain_length": 2, "task_owner_workload_score": 0.25,
         "is_blocked": 0, "risk_score": 0.18},
        {"avg_response_time_hrs": 0.5, "unanswered_mentions": 0,
         "dependency_chain_length": 1, "task_owner_workload_score": 0.05,
         "is_blocked": 0, "risk_score": 0.03},
    ]
    df = pd.DataFrame(base)
    df = _add_interaction_features(df)
    return df


# ─── Step 3: Training ─────────────────────────────────────────────────────────

def train(df: pd.DataFrame, golden: pd.DataFrame, oversample: int = 40):
    print("[3/5] Training …")

    # Inject golden data
    golden_rep = pd.concat([golden] * oversample, ignore_index=True)
    combined   = pd.concat([df, golden_rep], ignore_index=True)

    # Build features
    combined = _add_interaction_features(combined)

    # Strip non-feature columns (workspace_id, user_id, task_id)
    X_all = combined[FEATURE_COLS].copy()
    y_all = combined[TARGET_COL].copy()

    # Sample weights
    kaggle_w = np.ones(len(df))
    golden_w = np.full(len(golden_rep), 3.0)
    combined["_w"] = np.concatenate([kaggle_w, golden_w])
    combined = combined.sample(frac=1, random_state=42).reset_index(drop=True)
    w_all   = combined.pop("_w").values
    X_all   = combined[FEATURE_COLS].copy()
    y_all   = combined[TARGET_COL].copy()

    # Scale non-0-1 columns
    scaler = MinMaxScaler()
    X_all[SCALE_COLS] = scaler.fit_transform(X_all[SCALE_COLS])

    X_train, X_test, y_train, y_test, w_train, _ = train_test_split(
        X_all, y_all, w_all, test_size=0.20, random_state=42
    )

    # GridSearchCV — pruning-focused, 3-fold, 8 combos
    print("      GridSearchCV (3-fold, 8 combos) …")
    param_grid = {
        "n_estimators"    : [200, 400],
        "max_depth"       : [10, 15],
        "min_samples_leaf": [5, 10],
        "max_features"    : ["sqrt"],
    }
    cv     = KFold(n_splits=3, shuffle=True, random_state=42)
    search = GridSearchCV(
        RandomForestRegressor(random_state=42, n_jobs=-1),
        param_grid, cv=cv, scoring="r2", n_jobs=-1, refit=True, verbose=0,
    )
    search.fit(X_train, y_train, sample_weight=w_train)

    best_p    = search.best_params_
    best_cv_r2= search.best_score_

    print()
    print("  ┌─────────────────────────────────────────────────────┐")
    print("  │        GridSearchCV — Best Parameters               │")
    print("  ├─────────────────────────────────────────────────────┤")
    for k, v in best_p.items():
        print(f"  │  {k:<22s}: {str(v):<27s} │")
    print(f"  │  {'Best CV R²':<22s}: {best_cv_r2:<27.4f} │")
    print("  └─────────────────────────────────────────────────────┘")

    # Refit with oob_score for free generalisation estimate
    model = RandomForestRegressor(
        **{k: v for k, v in best_p.items()},
        oob_score=True, bootstrap=True, random_state=42, n_jobs=-1,
    )
    model.fit(X_train, y_train, sample_weight=w_train)
    print(f"      OOB R²: {model.oob_score_:.4f}")
    print(f"      Trained on {len(X_train):,} samples.")

    return model, scaler, X_train, y_train, X_test, y_test


# ─── Step 4: Evaluation + SHAP ────────────────────────────────────────────────

def evaluate(model, scaler, X_train, y_train, X_test, y_test):
    print("[4/5] Evaluation + SHAP …")

    y_pred_tr = model.predict(X_train)
    y_pred_te = model.predict(X_test)

    r2_tr  = r2_score(y_train, y_pred_tr)
    r2_te  = r2_score(y_test,  y_pred_te)
    mae    = mean_absolute_error(y_test, y_pred_te)
    gap    = r2_tr - r2_te
    flag   = "✅ Generalisation OK" if gap <= 0.05 else "⚠  Overfitting detected"
    oob    = getattr(model, "oob_score_", None)

    print()
    print("  ╔══════════════════════════════════════════════════╗")
    print(f"  ║  Train R²              : {r2_tr:.4f}                ║")
    print(f"  ║  Test  R²              : {r2_te:.4f}                ║")
    print(f"  ║  Train-Test Gap        : {gap:+.4f}                ║")
    if oob:
        print(f"  ║  OOB Score (R²)       : {oob:.4f}                ║")
    print(f"  ║  MAE                   : {mae:.4f}                ║")
    print(f"  ║  {flag:<48s}║")
    print("  ╚══════════════════════════════════════════════════╝")
    print()

    # SHAP
    explainer     = shap.TreeExplainer(model)
    shap_sample   = X_test.sample(min(400, len(X_test)), random_state=42)
    shap_vals     = explainer.shap_values(shap_sample)
    mean_shap = pd.Series(
        np.abs(shap_vals).mean(axis=0),
        index=FEATURE_COLS,
        name="mean_|SHAP|",
    ).sort_values(ascending=False)

    print("  ── SHAP Feature Importance ──")
    for feat, imp in mean_shap.items():
        bar = "█" * int(imp * 100)
        print(f"  {feat:<28s} {imp:.4f}  {bar}")
    print()

    # ── Plots ─────────────────────────────────────────────────────────────────
    # 1. Feature importance
    fig1, ax1 = plt.subplots(figsize=(10, 6))
    sns.barplot(x=mean_shap.values, y=mean_shap.index, ax=ax1,
                palette=sns.color_palette("coolwarm_r", n_colors=len(mean_shap)))
    ax1.set_xlabel("Mean |SHAP Value|", fontsize=12)
    ax1.set_title("Team Risk — SHAP Feature Importance", fontsize=14, fontweight="bold")
    for patch, val in zip(ax1.patches, mean_shap.values):
        ax1.text(patch.get_width() + 0.001, patch.get_y() + patch.get_height() / 2,
                 f"{val:.4f}", va="center", fontsize=9)
    plt.tight_layout()
    fig1.savefig(os.path.join(PLOTS_DIR, "team_feature_importance.png"), dpi=150)
    plt.close(fig1)

    # 2. Risk distribution
    fig2, ax2 = plt.subplots(figsize=(9, 5))
    sns.histplot(y_pred_te, bins=30, kde=True, color="#E74C3C",
                 edgecolor="white", ax=ax2)
    ax2.axvline(y_pred_te.mean(), color="#2C3E50", linestyle="--",
                linewidth=1.8, label=f"Mean = {y_pred_te.mean():.2f}")
    ax2.set_xlabel("Predicted Risk Score", fontsize=12)
    ax2.set_title("Team Risk Score Distribution (Test Set)", fontsize=14, fontweight="bold")
    ax2.legend()
    plt.tight_layout()
    fig2.savefig(os.path.join(PLOTS_DIR, "team_risk_distribution.png"), dpi=150)
    plt.close(fig2)

    # 3. Learning curve
    X_lc = pd.concat([X_train, X_test], ignore_index=True)
    y_lc = pd.concat([y_train, y_test], ignore_index=True)
    lc_rf = RandomForestRegressor(
        **{k: v for k, v in model.get_params().items()
           if k not in ("oob_score", "random_state", "n_jobs", "bootstrap")},
        oob_score=False, random_state=42, n_jobs=-1,
    )
    train_sizes, tr_scores, va_scores = learning_curve(
        lc_rf, X_lc, y_lc,
        train_sizes=np.linspace(0.1, 1.0, 7), cv=3,
        scoring="r2", n_jobs=-1, shuffle=True, random_state=42,
    )
    fig3, ax3 = plt.subplots(figsize=(9, 5))
    ax3.plot(train_sizes, tr_scores.mean(axis=1), "o-", color="#2ECC71", label="Train R²")
    ax3.fill_between(train_sizes,
                     tr_scores.mean(axis=1) - tr_scores.std(axis=1),
                     tr_scores.mean(axis=1) + tr_scores.std(axis=1),
                     alpha=0.15, color="#2ECC71")
    ax3.plot(train_sizes, va_scores.mean(axis=1), "o-", color="#E74C3C", label="Validation R²")
    ax3.fill_between(train_sizes,
                     va_scores.mean(axis=1) - va_scores.std(axis=1),
                     va_scores.mean(axis=1) + va_scores.std(axis=1),
                     alpha=0.15, color="#E74C3C")
    ax3.axhline(0.85, color="#95A5A6", linestyle=":", linewidth=1.2, label="Target = 0.85")
    ax3.set_xlabel("Training Set Size", fontsize=12)
    ax3.set_ylabel("R² Score", fontsize=12)
    ax3.set_title("Learning Curve — Team Risk Model", fontsize=14, fontweight="bold")
    ax3.legend(); ax3.set_ylim(0, 1.05)
    plt.tight_layout()
    fig3.savefig(os.path.join(PLOTS_DIR, "team_learning_curve.png"), dpi=150)
    plt.close(fig3)

    print(f"  Plots saved → {PLOTS_DIR}")
    return explainer, mean_shap


# ─── Step 5: Export + predict_risk() ─────────────────────────────────────────

def export(model, scaler):
    joblib.dump(model,  MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    print(f"  Saved → {MODEL_PATH}")
    print(f"  Saved → {SCALER_PATH}")


def predict_risk(data: dict, model, scaler, explainer) -> dict:
    """
    Deployment-ready inference for a single task/user record.

    Required input keys
    -------------------
    avg_response_time_hrs      float  hours since last response
    unanswered_mentions        int    number of @mentions ignored
    dependency_chain_length    int    hops in the dependency graph
    task_owner_workload_score  float  0-1 current owner workload
    is_blocked                 int    0 or 1

    Returns
    -------
    dict: risk_score, risk_level, reason, shap_values
    """
    defaults = {
        "avg_response_time_hrs": 4.0,
        "unanswered_mentions": 0,
        "dependency_chain_length": 2,
        "task_owner_workload_score": 0.3,
        "is_blocked": 0,
    }
    row = pd.DataFrame([{k: data.get(k, defaults[k]) for k in defaults}])
    row = _add_interaction_features(row)

    X_row = row[FEATURE_COLS].copy()
    X_row[SCALE_COLS] = scaler.transform(X_row[SCALE_COLS])
    X_row.replace([np.inf, -np.inf], np.nan, inplace=True)
    X_row.fillna(0.0, inplace=True)

    score     = float(np.clip(model.predict(X_row)[0], 0.0, 1.0))
    shap_raw  = explainer.shap_values(X_row)[0]
    shap_dict = dict(zip(FEATURE_COLS, shap_raw.tolist()))
    top_feat  = max(shap_dict, key=lambda k: abs(shap_dict[k]))
    reason    = REASON_TEMPLATES.get(top_feat, f"Primary driver: {top_feat}.")

    return {
        "risk_score" : round(score, 2),
        "risk_level" : _resolve_level(score),
        "reason"     : reason,
        "shap_values": {k: round(v, 4) for k, v in shap_dict.items()},
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print()
    print("=" * 60)
    print("  Team Risk Engine — ml_3_risk_scoring")
    print("=" * 60)
    print()

    print("[1/5] Loading data …")
    df     = load_data()
    golden = build_golden_data()

    model, scaler, X_train, y_train, X_test, y_test = train(df, golden)
    explainer, mean_shap = evaluate(model, scaler, X_train, y_train, X_test, y_test)

    print("[5/5] Exporting artefacts …")
    export(model, scaler)

    # Demo
    print()
    print("─" * 60)
    print("  predict_risk() — Demo Scenarios")
    print("─" * 60)
    demos = [
        {"label": "🔴 CRITICAL — ignored pings + silent owner",
         "avg_response_time_hrs": 60, "unanswered_mentions": 8,
         "dependency_chain_length": 7, "task_owner_workload_score": 0.95, "is_blocked": 1},
        {"label": "🟡 MEDIUM — moderate delay",
         "avg_response_time_hrs": 14, "unanswered_mentions": 2,
         "dependency_chain_length": 3, "task_owner_workload_score": 0.55, "is_blocked": 0},
        {"label": "🟢 LOW — healthy team",
         "avg_response_time_hrs": 1, "unanswered_mentions": 0,
         "dependency_chain_length": 1, "task_owner_workload_score": 0.10, "is_blocked": 0},
    ]
    for d in demos:
        label = d.pop("label")
        out   = predict_risk(d, model, scaler, explainer)
        print(f"\n  {label}")
        print(f"  Input : {d}")
        print(f"  Output: {json.dumps(out, indent=4)}")

    print()
    print("=" * 60)
    print("  All steps complete.")
    print(f"  Model artefacts → {ARTIFACTS_DIR}")
    print(f"  Plots           → {PLOTS_DIR}")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
