"""
demo.py — ML Engineer 2: Task Similarity Engine
AI-Driven Project Intelligence for Engineering Teams (Hackathon)

Run:
    python demo.py

Shows the full pipeline: load tasks → receive new chat message → classify similarity.
"""

import json
import sys
import os

# Allow running from this folder directly
sys.path.insert(0, os.path.dirname(__file__))

from task_similarity import Task, TaskSimilarityEngine


def load_sample_tasks(path: str = "sample_tasks.json"):
    """Load existing tasks from the sample JSON file."""
    with open(path, "r") as f:
        data = json.load(f)
    return [
        Task(
            id=t["id"],
            title=t["title"],
            description=t["description"],
            past_outcome=t["past_outcome"],
        )
        for t in data
    ]


def run_demo():
    print("=" * 60)
    print("ML ENGINEER 2 — TASK SIMILARITY ENGINE")
    print("AI-Driven Project Intelligence for Engineering Teams")
    print("=" * 60)

    # ── Step 1: Load existing tasks (would come from DB in production) ────────
    tasks = load_sample_tasks()
    engine = TaskSimilarityEngine()
    engine.add_tasks(tasks)

    print("\nExisting tasks in the system:")
    for t in tasks:
        print(f"  [{t.id}] {t.title}  (outcome: {t.past_outcome})")

    # ── Step 2: Simulate messages extracted by ML Engineer 1 ─────────────────
    incoming_messages = [
        "Authentication service is broken - users can't login",   # → DUPLICATE/RELATED
        "Add dark mode support to the UI",                        # → NEW
        "Database queries are too slow on the dashboard page",    # → DUPLICATE/RELATED
    ]

    for message in incoming_messages:
        print("\n" + "-" * 60)
        print(f"INCOMING TASK: '{message}'")
        print("-" * 60)

        results = engine.find_similar_tasks(message, threshold=0.30)

        if not results:
            print("→ Classification: NEW TASK (no similar tasks found)")
        else:
            for r in results:
                print(f"\n  Match → Task [{r['task_id']}]: {r['task_text'][:65]}...")
                print(f"  TF-IDF Score   : {r['tfidf_similarity']:.3f}")
                print(f"  Semantic Score : {r['semantic_similarity']:.3f}")
                print(f"  Final Score    : {r['final_similarity_score']:.3f}")
                print(f"  Label          : {r['label']}")
                print(f"  Past Outcome   : {r['past_outcome']}")

                if r["label"] == "DUPLICATE":
                    print("  ⚠  ACTION: Block task creation — likely duplicate")
                elif r["label"] == "RELATED":
                    print("  →  ACTION: Allow creation, link to this task")

    print("\n" + "=" * 60)
    print("JUDGE NOTES:")
    print("  • TF-IDF  = keyword overlap (fast, explainable)")
    print("  • Semantic = deep meaning via all-MiniLM-L6-v2")
    print("  • Final   = 0.5 × TF-IDF + 0.5 × Semantic")
    print("  • Scores feed directly into ML-3 risk prediction")
    print("=" * 60)


if __name__ == "__main__":
    run_demo()
