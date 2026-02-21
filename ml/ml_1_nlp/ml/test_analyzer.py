import sys
import json

# Ensure local ml package path is first
sys.path.insert(0, r'e:/parth/Loop/AI-Driven-Project-Management/ml/ml_1_nlp/ml')
from nlp_classifier import analyze_conversation

EXAMPLES = [
    {
        "name": "Basic task mention + link",
        "payload": {
            "workspace_id": "w1",
            "channel_id": "c1",
            "user_id": "u1",
            "timestamp": "2026-02-21T12:00:00",
            "last_n_messages": [
                {"message_id": "msg_21", "user_id": "u2", "text": "We need to fix the payment bug by tomorrow", "timestamp": "2026-02-21T11:50:00"},
                {"message_id": "msg_22", "user_id": "u3", "text": "Assign this to @john please", "timestamp": "2026-02-21T11:55:00"}
            ],
            "current_message": "Is that bug still open?",
            "existing_tasks": [{"task_id": "T1", "title": "payment bug fix"}]
        }
    },
    {
        "name": "Ownership + channel ref",
        "payload": {
            "workspace_id": "w1",
            "channel_id": "backend",
            "user_id": "u4",
            "timestamp": "2026-02-22T09:00:00",
            "last_n_messages": [
                {"message_id": "msg_30", "user_id": "u5", "text": "@sara can you take this?", "timestamp": "2026-02-22T08:50:00"},
                {"message_id": "msg_31", "user_id": "u6", "text": "Please move discussion to #backend and assign to @sara", "timestamp": "2026-02-22T08:55:00"}
            ],
            "current_message": "sara, you take this",
            "existing_tasks": []
        }
    },
    {
        "name": "User-linked deadline",
        "payload": {
            "workspace_id": "w1",
            "channel_id": "c2",
            "user_id": "u7",
            "timestamp": "2026-02-23T10:15:00",
            "last_n_messages": [
                {"message_id": "msg_40", "user_id": "u8", "text": "Parth by Friday please", "timestamp": "2026-02-23T09:00:00"}
            ],
            "current_message": "parth by friday",
            "existing_tasks": []
        }
    },
    {
        "name": "Pronoun linking to previous task",
        "payload": {
            "workspace_id": "w1",
            "channel_id": "c3",
            "user_id": "u9",
            "timestamp": "2026-02-24T14:00:00",
            "last_n_messages": [
                {"message_id": "msg_50", "user_id": "u10", "text": "Created task: OAuth login bug (task_102)", "timestamp": "2026-02-24T13:45:00"},
                {"message_id": "msg_51", "user_id": "u9", "text": "That bug is still open", "timestamp": "2026-02-24T13:50:00"}
            ],
            "current_message": "Can someone check?",
            "existing_tasks": [{"task_id": "task_102", "title": "OAuth login bug"}]
        }
    }
]


def run_examples():
    for ex in EXAMPLES:
        print("\n===== Example: {} =====".format(ex["name"]))
        payload = ex["payload"]
        print("Payload:")
        print(json.dumps(payload, indent=2))
        result = analyze_conversation(payload)
        print("\nResult:")
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    run_examples()
