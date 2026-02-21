"""
team_risk.py
============
Workspace-level risk aggregation engine.

Aggregates individual task risk scores per workspace and applies a
bottleneck penalty derived from the interaction graph to produce a
final workspace_risk_score ∈ [0, 1].

Formula
-------
workspace_risk = clip(
    base_risk + BOTTLENECK_WEIGHT * bottleneck_penalty
    + SPREAD_WEIGHT * risk_spread,
    0, 1
)
  where:
    base_risk         = mean(task risk scores in workspace)
    bottleneck_penalty= interaction_graph.workspace_bottleneck_penalty(ws)
    risk_spread       = std(task risk scores) — high variance = unstable team

Risk Levels
-----------
  Critical  ≥ 0.85
  High      ≥ 0.65
  Medium    ≥ 0.40
  Low       < 0.40

Usage
-----
    from team_risk import WorkspaceRiskAggregator

    aggregator = WorkspaceRiskAggregator(df, model, scaler, explainer)
    report = aggregator.compute_all()
    print(report)
"""

import warnings
import numpy  as np
import pandas as pd

from interaction_graph import TeamInteractionGraph

# Penalty weights (sum to 1 with base risk effectively being weight 1.0 floor)
BOTTLENECK_WEIGHT = 0.15   # how much a bottleneck user adds to workspace risk
SPREAD_WEIGHT     = 0.05   # penalise high variance teams (unpredictability)

RISK_BANDS = [
    (0.85, "Critical"),
    (0.65, "High"),
    (0.40, "Medium"),
    (0.00, "Low"),
]


def _resolve_level(score: float) -> str:
    for threshold, label in RISK_BANDS:
        if score >= threshold:
            return label
    return "Low"


class WorkspaceRiskAggregator:
    """
    Compute risk_score_per_workspace for all workspaces in a DataFrame.

    Parameters
    ----------
    df          : pd.DataFrame — team task data (must have 'risk_score' column
                  pre-computed by the ML model or the formula in generate_team_data)
    graph       : TeamInteractionGraph or None — if None, penalty = 0
    """

    def __init__(self, df: pd.DataFrame,
                 graph: TeamInteractionGraph = None):
        self.df    = df.copy()
        self.graph = graph

    # ─── Core computation ─────────────────────────────────────────────────────

    def _workspace_risk(self, ws_id: str) -> dict:
        ws_df = self.df[self.df["workspace_id"] == ws_id]
        if ws_df.empty:
            return {}

        base_risk    = ws_df["risk_score"].mean()
        risk_spread  = ws_df["risk_score"].std()
        n_tasks      = len(ws_df)
        n_users      = ws_df["user_id"].nunique()
        blocked_pct  = ws_df["is_blocked"].mean() * 100

        # Bottleneck penalty from interaction graph
        bn_penalty = 0.0
        if self.graph is not None:
            bn_penalty = self.graph.workspace_bottleneck_penalty(ws_id)

        raw_score = (
            base_risk
            + BOTTLENECK_WEIGHT * bn_penalty
            + SPREAD_WEIGHT * min(risk_spread, 1.0)
        )
        final_score = float(np.clip(raw_score, 0.0, 1.0))

        return {
            "workspace_id"       : ws_id,
            "workspace_risk_score": round(final_score, 4),
            "risk_level"         : _resolve_level(final_score),
            "base_risk"          : round(float(base_risk), 4),
            "bottleneck_penalty" : round(float(bn_penalty), 4),
            "risk_spread"        : round(float(risk_spread), 4),
            "n_tasks"            : n_tasks,
            "n_users"            : n_users,
            "blocked_pct"        : round(float(blocked_pct), 1),
        }

    def compute_all(self) -> pd.DataFrame:
        """
        Compute workspace risk for every unique workspace_id.

        Returns
        -------
        pd.DataFrame sorted by workspace_risk_score descending.
        """
        workspaces = self.df["workspace_id"].unique()
        records    = [self._workspace_risk(ws) for ws in workspaces]
        report     = pd.DataFrame([r for r in records if r])
        report     = report.sort_values("workspace_risk_score", ascending=False)
        report     = report.reset_index(drop=True)
        return report

    def top_at_risk(self, n: int = 5) -> pd.DataFrame:
        """Return top-N highest-risk workspaces."""
        return self.compute_all().head(n)

    def print_report(self, n: int | None = None) -> None:
        """Print a formatted risk report to console."""
        report = self.compute_all()
        if n:
            report = report.head(n)

        print()
        print("=" * 68)
        print("  WORKSPACE RISK REPORT")
        print("=" * 68)
        print(f"  {'Workspace':<10} {'Score':>6}  {'Level':<10} "
              f"{'Base':>6}  {'BN Pen':>6}  {'Blocked%':>8}  {'Users':>5}")
        print("-" * 68)
        for _, row in report.iterrows():
            level_tag = {
                "Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"
            }.get(row["risk_level"], "")
            print(
                f"  {row['workspace_id']:<10} {row['workspace_risk_score']:>6.4f}  "
                f"{level_tag} {row['risk_level']:<8} {row['base_risk']:>6.4f}  "
                f"{row['bottleneck_penalty']:>6.4f}  {row['blocked_pct']:>7.1f}%  "
                f"{row['n_users']:>5}"
            )
        print("=" * 68)
        print()


if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(__file__))

    from synthetic_data.generate_team_data import generate

    print("Generating synthetic data …")
    df = generate(2000)

    print("Building interaction graph …")
    graph = TeamInteractionGraph(df)

    print("Computing workspace risk …")
    aggregator = WorkspaceRiskAggregator(df, graph)
    aggregator.print_report()

    top = aggregator.top_at_risk(5)
    print("Top-5 highest-risk workspaces:")
    print(top[["workspace_id", "workspace_risk_score",
               "risk_level", "bottleneck_penalty", "blocked_pct"]].to_string(index=False))
