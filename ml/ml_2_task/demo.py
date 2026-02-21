"""demo.py — Task Similarity Engine: multi-user, multi-workspace demo."""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from task_similarity import Task, TaskSimilarityEngine
from task_linking import TaskLinkingEngine, link_message_to_task, get_task_by_message


def load_sample_tasks(path: str = "sample_tasks.json"):
    with open(path, "r") as f:
        data = json.load(f)
    return [
        Task(
            id=t["id"],
            title=t["title"],
            description=t["description"],
            past_outcome=t["past_outcome"],
            workspace_id=t["workspace_id"],
            project_id=t.get("project_id"),
            assigned_user_id=t.get("assigned_user_id"),
        )
        for t in data
    ]


def run_demo():
    print("=" * 80)
    print("ML ENGINEER 2 — ENHANCED TASK SIMILARITY ENGINE")
    print("Multi-User, Multi-Workspace Task Intelligence")
    print("=" * 80)

    # ── Step 1: Load existing tasks and initialize engines ──────────────────
    tasks = load_sample_tasks()
    similarity_engine = TaskSimilarityEngine()
    similarity_engine.add_tasks(tasks)
    linking_engine = TaskLinkingEngine()

    print("\nExisting tasks in the system:")
    workspaces = {}
    for t in tasks:
        if t.workspace_id not in workspaces:
            workspaces[t.workspace_id] = []
        workspaces[t.workspace_id].append(t)
    
    for ws_id, ws_tasks in workspaces.items():
        print(f"\n  Workspace: {ws_id}")
        for t in ws_tasks:
            project_info = f"/{t.project_id}" if t.project_id else ""
            user_info = f" (assigned: {t.assigned_user_id})" if t.assigned_user_id else ""
            print(f"    [{t.id}] {t.title}{project_info}{user_info}")

    # ── Step 2: Simulate multi-user messages with workspace context ─────────
    test_scenarios = [
        {
            "message": "OAuth login is completely broken",
            "workspace_id": "project-alpha",
            "project_id": "auth-system",
            "user_context": {"sender_id": "user999", "mentioned_users": [], "conversation_context": []},
            "message_id": "msg_001"
        },
        {
            "message": "Dashboard loads super slowly",
            "workspace_id": "project-alpha",
            "project_id": "dashboard",
            "user_context": {"sender_id": "user888", "mentioned_users": ["user456"], "conversation_context": []},
            "message_id": "msg_002"
        },
        {
            "message": "Need to add dark mode feature",
            "workspace_id": "project-alpha",
            "project_id": "dashboard",
            "user_context": {"sender_id": "user777", "mentioned_users": [], "conversation_context": []},
            "message_id": "msg_003"
        },
        {
            "message": "CI/CD pipeline setup required",
            "workspace_id": "project-gamma",
            "project_id": "devops",
            "user_context": {"sender_id": "user666", "mentioned_users": ["user123", "user456"], "conversation_context": []},
            "message_id": "msg_004"
        }
    ]

    for scenario in test_scenarios:
        print("\n" + "-" * 80)
        print(f"INCOMING MESSAGE: '{scenario['message']}'")
        print(f"Workspace: {scenario['workspace_id']}, Project: {scenario['project_id']}")
        print(f"From: {scenario['user_context']['sender_id']}")
        if scenario['user_context']['mentioned_users']:
            print(f"Mentions: {scenario['user_context']['mentioned_users']}")
        print("-" * 80)

        existing_task = get_task_by_message(scenario['message_id'])
        if existing_task:
            print(f"→ MESSAGE ALREADY LINKED TO TASK {existing_task}")
            continue

        result = similarity_engine.find_similar_tasks(
            new_task_text=scenario['message'],
            workspace_id=scenario['workspace_id'],
            project_id=scenario['project_id'],
            user_context=scenario['user_context']
        )

        print(f"\nDECISION: {result['decision'].upper()}")
        print(f"Confidence: {result['confidence']:.3f}")
        if result['assigned_user_id']:
            print(f"Task Assignment: {result['assigned_user_id']}")
        else:
            print("Task Assignment: Unassigned (manual review needed)")
        
        if result['decision'] == 'auto_link':
            print(f"🔗 AUTO-LINKING to existing Task [{result['matched_task_id']}]")
            link_message_to_task(scenario['message_id'], str(result['matched_task_id']), scenario['workspace_id'], scenario['project_id'])
        elif result['decision'] == 'suggest':
            print(f"💡 SUGGESTING relation to Task [{result['matched_task_id']}] (needs confirmation)")
        else:
            print("✨ CREATING NEW TASK")
            new_task_id = f"new_task_{len(tasks) + 1}"
            link_message_to_task(scenario['message_id'], new_task_id, scenario['workspace_id'], scenario['project_id'])

        # Show similar tasks found within scope
        if result['similar_tasks']:
            print(f"\nSimilar tasks found in {scenario['workspace_id']}:")
            for task in result['similar_tasks'][:3]:  # Show top 3
                print(f"  [{task['task_id']}] Score: {task['final_similarity_score']:.3f}")
                print(f"      {task['task_text'][:60]}...")
                if task.get('assigned_user_id'):
                    print(f"      Assigned: {task['assigned_user_id']}")

    # ── Step 3: Demonstrate cross-workspace isolation ──────────────────────
    print("\n" + "=" * 80)
    print("CROSS-WORKSPACE ISOLATION DEMO")
    print("=" * 80)
    
    # Same task text, different workspaces
    cross_workspace_test = {
        "message": "Fix authentication bugs",
        "user_context": {"sender_id": "user555", "mentioned_users": [], "conversation_context": []}
    }
    
    for workspace in ["project-alpha", "project-beta", "project-gamma"]:
        result = similarity_engine.find_similar_tasks(
            new_task_text=cross_workspace_test['message'],
            workspace_id=workspace,
            user_context=cross_workspace_test['user_context']
        )
        print(f"\nWorkspace {workspace}: {result['decision']} (confidence: {result['confidence']:.3f})")
        print(f"  Similar tasks found: {len(result['similar_tasks'])}")

    print("\n" + "=" * 80)
    print("SUMMARY OF ENHANCEMENTS:")
    print("  ✅ Workspace/Project scoping prevents false duplicates")
    print("  ✅ Smart confidence thresholds reduce noise")  
    print("  ✅ Rule-based task ownership assignment")
    print("  ✅ Message-to-task linking prevents re-creation")
    print("  ✅ Backward-compatible with existing ML logic")
    print("=" * 80)


if __name__ == "__main__":
    run_demo()
