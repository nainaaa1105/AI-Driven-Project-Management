"""
interaction_graph.py
====================
Directed dependency graph for team interactions using NetworkX.

Nodes  = user_ids
Edges  = directed dependency (user_a depends on user_b for a task)
Weights= dependency_chain_length on the edge

Key outputs:
  - Bottleneck users: those with high IN-degree centrality
    (many people waiting on them) → blocking multiplier
  - Per-user bottleneck score ∈ [0, 1] for use as a penalty in team_risk.py

Usage:
    from interaction_graph import TeamInteractionGraph

    graph = TeamInteractionGraph(df)   # df from generate_team_data.py
    print(graph.bottleneck_scores())
    print(graph.top_bottlenecks(n=5))
"""

import warnings
from typing import Optional
import numpy  as np
import pandas as pd

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False
    warnings.warn(
        "networkx not installed. Run: pip install networkx\n"
        "TeamInteractionGraph will fall back to a zero-score stub.",
        ImportWarning,
    )


class TeamInteractionGraph:
    """
    Builds a directed weighted graph from task dependency data.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: user_id, task_id, dependency_chain_length,
        workspace_id, is_blocked.
    workspace_id : str or None
        If given, filter to only that workspace before building the graph.
    """

    def __init__(self, df: pd.DataFrame, workspace_id: Optional[str] = None):
        self._df = df.copy()
        if workspace_id:
            self._df = self._df[self._df["workspace_id"] == workspace_id]

        self.graph: Optional["nx.DiGraph"] = None
        self._centrality: dict = {}

        if HAS_NX:
            self._build()

    # ─── Graph Construction ───────────────────────────────────────────────────

    def _build(self) -> None:
        """
        Edge construction strategy
        --------------------------
        For each task that is_blocked, we infer a dependency edge:
          assignee_user  →  "blocking_user"

        Since we don't have an explicit blocker column in synthetic data,
        we approximate: blocked tasks → the user who owns the longest
        dependency chain in the same workspace is likely the bottleneck.

        For non-blocked tasks, we still add self-loop weight to represent
        workload concentration.
        """
        G = nx.DiGraph()

        # Add all users as nodes with workload attribute
        for _, row in self._df.iterrows():
            uid = row["user_id"]
            if not G.has_node(uid):
                G.add_node(uid, workload=0.0, blocked_tasks=0)
            G.nodes[uid]["workload"]      += row["task_owner_workload_score"]
            G.nodes[uid]["blocked_tasks"] += int(row["is_blocked"])

        # Add dependency edges: for blocked tasks, connect to the user in the
        # same workspace with the highest avg dependency chain (proxy for blocker)
        ws_groups = self._df.groupby("workspace_id")
        for ws_id, ws_df in ws_groups:
            if ws_df["is_blocked"].sum() == 0:
                continue

            # User most likely to be bottleneck: highest mean dep chain length
            bottleneck_uid = (
                ws_df.groupby("user_id")["dependency_chain_length"]
                .mean()
                .idxmax()
            )

            blocked_rows = ws_df[ws_df["is_blocked"] == 1]
            for _, brow in blocked_rows.iterrows():
                src = brow["user_id"]
                dst = bottleneck_uid
                if src == dst:
                    continue
                weight = float(brow["dependency_chain_length"])
                if G.has_edge(src, dst):
                    G[src][dst]["weight"] += weight
                else:
                    G.add_edge(src, dst, weight=weight)

        self.graph = G

        # In-degree centrality: fraction of all nodes that point TO this node
        # High in-degree → many people are waiting on this user → bottleneck
        self._centrality = nx.in_degree_centrality(G) if len(G) > 0 else {}

    # ─── Public API ──────────────────────────────────────────────────────────

    def bottleneck_scores(self) -> pd.Series:
        """
        Return a Series[user_id → bottleneck_score ∈ [0,1]].
        Score is the normalised in-degree centrality.
        """
        if not HAS_NX or not self._centrality:
            users = self._df["user_id"].unique()
            return pd.Series(np.zeros(len(users)), index=users, name="bottleneck_score")

        scores = pd.Series(self._centrality, name="bottleneck_score")
        max_val = scores.max()
        if max_val > 0:
            scores = scores / max_val       # normalise to [0, 1]
        return scores

    def top_bottlenecks(self, n: int = 5) -> pd.DataFrame:
        """Return top-N bottleneck users as a DataFrame with score and workload."""
        scores = self.bottleneck_scores().sort_values(ascending=False).head(n)
        result = scores.reset_index()
        result.columns = ["user_id", "bottleneck_score"]

        # Attach average workload
        workload_map = (
            self._df.groupby("user_id")["task_owner_workload_score"]
            .mean()
            .rename("avg_workload")
        )
        result = result.join(workload_map, on="user_id")
        return result

    def workspace_bottleneck_penalty(self, workspace_id: str) -> float:
        """
        Returns a 0-1 penalty for a workspace based on how concentrated
        its dependency graph is. Higher = more bottleneck risk.
        """
        ws_df = self._df[self._df["workspace_id"] == workspace_id]
        if ws_df.empty:
            return 0.0

        # Fraction of blocked tasks in this workspace
        block_fraction = ws_df["is_blocked"].mean()

        # Average bottleneck score of users in this workspace
        scores = self.bottleneck_scores()
        ws_users = ws_df["user_id"].unique()
        relevant = scores.reindex(ws_users).fillna(0.0)
        avg_centrality = relevant.mean()

        # Combined penalty: 60% centrality, 40% block fraction
        penalty = 0.60 * avg_centrality + 0.40 * block_fraction
        return float(np.clip(penalty, 0.0, 1.0))

    def summary(self) -> None:
        """Print graph statistics."""
        if not HAS_NX or self.graph is None:
            print("  Graph not available (networkx missing).")
            return
        G = self.graph
        print(f"  Nodes (users)     : {G.number_of_nodes()}")
        print(f"  Edges (deps)      : {G.number_of_edges()}")
        top = self.top_bottlenecks(3)
        print("  Top-3 bottlenecks:")
        for _, row in top.iterrows():
            print(f"    {row['user_id']}  score={row['bottleneck_score']:.3f}  "
                  f"workload={row.get('avg_workload', 0):.3f}")


if __name__ == "__main__":
    from synthetic_data.generate_team_data import generate
    df = generate(500)
    print("Building interaction graph …")
    ig = TeamInteractionGraph(df)
    ig.summary()
    print("\nTop-5 bottleneck users:")
    print(ig.top_bottlenecks(5).to_string(index=False))
