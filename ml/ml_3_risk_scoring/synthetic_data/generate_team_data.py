"""
generate_team_data.py
=====================
Synthetic multi-user, Discord-style team dataset generator.

Generates 2,000 rows simulating project workspaces with multiple users,
tasks, and communication patterns. Risk score increases significantly when:
  - unanswered_mentions > 3 (team member is being ignored)
  - avg_response_time_hrs > 24 (slow async communication)
  - is_blocked = 1 AND dependency_chain_length > 3 (cascading blockers)

Output: ./team_task_data.csv (relative to this script's location)
"""

import os
import numpy as np
import pandas as pd

np.random.seed(42)

# ─── Config ──────────────────────────────────────────────────────────────────
N_ROWS       = 2_000
N_WORKSPACES = 20      # 20 distinct workspace channels (like Discord servers)
N_USERS      = 50      # 50 distinct user IDs across all workspaces
N_TASKS      = 300     # task pool


def _compute_risk(row: dict) -> float:
    """
    Physics-based risk formula for team interactions.

    Weights (sum to 1.0):
        0.25 — avg_response_time_hrs  (slow response = disengagement)
        0.25 — unanswered_mentions    (ignored pings = coordination failure)
        0.20 — task_owner_workload    (overloaded owner = delivery risk)
        0.15 — is_blocked             (hard blocker flag)
        0.15 — dependency_chain_length(long chains amplify delays)
    """
    # Normalise inputs to [0, 1]
    resp_norm  = min(row["avg_response_time_hrs"] / 72.0, 1.0)   # cap at 72 hrs
    mention_norm = min(row["unanswered_mentions"] / 10.0, 1.0)   # cap at 10
    dep_norm   = min(row["dependency_chain_length"] / 8.0, 1.0)  # cap at 8
    workload   = row["task_owner_workload_score"]                 # already 0-1
    blocked    = float(row["is_blocked"])

    base = (
        0.25 * resp_norm
        + 0.25 * mention_norm
        + 0.20 * workload
        + 0.15 * blocked
        + 0.15 * dep_norm
    )

    # ── Critical trigger boosts ───────────────────────────────────────────
    # Rule 1: unanswered_mentions > 3 → strong upward push
    if row["unanswered_mentions"] > 3:
        base += 0.20

    # Rule 2: avg_response_time_hrs > 24 → strong upward push
    if row["avg_response_time_hrs"] > 24:
        base += 0.18

    # Rule 3: blocked + long dependency chain → cascade amplifier
    if row["is_blocked"] and row["dependency_chain_length"] > 3:
        base += 0.15

    # Add small Gaussian noise for realism
    base += np.random.normal(0, 0.02)

    return float(np.clip(base, 0.0, 1.0))


def generate(n: int = N_ROWS) -> pd.DataFrame:
    workspace_ids = [f"WS-{i:03d}" for i in range(1, N_WORKSPACES + 1)]
    user_ids      = [f"U-{i:04d}"  for i in range(1, N_USERS + 1)]
    task_ids      = [f"T-{i:05d}"  for i in range(1, N_TASKS + 1)]

    rows = []
    for _ in range(n):
        ws  = np.random.choice(workspace_ids)
        usr = np.random.choice(user_ids)
        tsk = np.random.choice(task_ids)

        # ── Communication signals ─────────────────────────────────────────
        # 80 % of responses are within 12 hrs; 20 % are slow (12-72 hrs)
        if np.random.rand() < 0.80:
            avg_resp = round(np.random.exponential(scale=4.0), 2)   # fast
        else:
            avg_resp = round(np.random.uniform(12.0, 72.0), 2)      # slow

        # Unanswered mentions: mostly 0-3, occasionally spike
        if np.random.rand() < 0.75:
            mentions = int(np.random.randint(0, 4))
        else:
            mentions = int(np.random.randint(4, 12))                # spike

        dep_chain = int(np.random.randint(1, 9))                    # 1-8 hops
        workload  = round(np.random.beta(2, 3), 4)                  # skewed low
        is_blocked = int(np.random.rand() < 0.25)                   # 25 % blocked

        row = {
            "workspace_id"              : ws,
            "user_id"                   : usr,
            "task_id"                   : tsk,
            "avg_response_time_hrs"     : avg_resp,
            "unanswered_mentions"       : mentions,
            "dependency_chain_length"   : dep_chain,
            "task_owner_workload_score" : workload,
            "is_blocked"                : is_blocked,
        }
        row["risk_score"] = _compute_risk(row)
        rows.append(row)

    df = pd.DataFrame(rows)
    return df


if __name__ == "__main__":
    print("Generating 2,000-row synthetic team dataset …")
    df = generate()
    out_dir = os.path.join(os.path.dirname(__file__))
    out_path = os.path.join(out_dir, "team_task_data.csv")
    df.to_csv(out_path, index=False)

    print(f"  Saved  : {out_path}")
    print(f"  Shape  : {df.shape}")
    print(f"  Risk   : mean={df['risk_score'].mean():.3f}  "
          f"min={df['risk_score'].min():.3f}  max={df['risk_score'].max():.3f}")

    # Quick sanity: rows where both triggers fire should average > 0.7
    triggered = df[
        (df["unanswered_mentions"] > 3) & (df["avg_response_time_hrs"] > 24)
    ]
    print(f"  Trigger check ({len(triggered)} dual-trigger rows): "
          f"mean risk = {triggered['risk_score'].mean():.3f}  (expected > 0.70)")
    print("Done.")
