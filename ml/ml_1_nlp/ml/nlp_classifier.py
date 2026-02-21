import torch
import re
from datetime import datetime
from transformers import pipeline
try:
    from ml.entity_extractor import EntityExtractor
except Exception:
    from entity_extractor import EntityExtractor

class MessageClassifier:
    def __init__(self, model_name="typeform/distilbert-base-uncased-mnli"):
        """
        Initialize the classifier. Using a zero-shot classification model 
        as it allows classifying into arbitrary labels without specific training.
        For production, you would fine-tune distilbert-base-uncased on your labeled data.
        """
        self.device = 0 if torch.cuda.is_available() else -1
        self.classifier = pipeline("zero-shot-classification", 
                                   model=model_name, 
                                   device=self.device)
        self.intent_labels = [
            "task mention", "blocker", "risk", "dependency", 
            "positive progress", "milestone achieved", "general message status"
        ]
        self.event_labels = [
            "bug fix", "feature development", "deployment", 
            "meeting", "code review", "research", "testing", "documentation"
        ]
        self.domain_labels = [
            "frontend", "backend", "devops", "database", 
            "design", "security", "product", "infrastructure"
        ]

    def _classify_list(self, text, labels, threshold=0.4, template="This message is about {}."):
        result = self.classifier(text, 
                                 candidate_labels=labels, 
                                 hypothesis_template=template,
                                 multi_label=True)
        hits = []
        for label, score in zip(result['labels'], result['scores']):
            if score >= threshold:
                hits.append({"label": label, "confidence": round(float(score), 4)})
        
        if not hits:
            hits.append({"label": result['labels'][0], "confidence": round(float(result['scores'][0]), 4)})
        return hits

    def classify_all(self, text):
        return {
            "intents": self._classify_list(text, self.intent_labels, threshold=0.5, template="This message represents a {}."),
            "event_types": self._classify_list(text, self.event_labels, threshold=0.4, template="This is a {} event."),
            "domains": self._classify_list(text, self.domain_labels, threshold=0.4, template="This relates to the {} domain.")
        }


def group_conversation(messages, window=10):
    """
    Groups messages into ordered context windows for AI reasoning.
    messages: list of dicts with keys `user_id`, `text`, `timestamp`, `message_id` (optional)
    Returns list of chunks: {"start_ts","end_ts","participants", "messages"}
    """
    # Normalize and sort by timestamp
    def parse_ts(m):
        ts = m.get("timestamp")
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts)
            except Exception:
                return datetime.utcnow()
        return ts or datetime.utcnow()

    msgs = sorted(messages, key=parse_ts)
    chunks = []
    for i in range(0, len(msgs), max(1, window)):
        window_msgs = msgs[i:i+window]
        participants = list({m.get("user_id") for m in window_msgs if m.get("user_id")})
        chunk = {
            "start_ts": parse_ts(window_msgs[0]).isoformat(),
            "end_ts": parse_ts(window_msgs[-1]).isoformat(),
            "participants": participants,
            "messages": [
                {"user_id": m.get("user_id"), "text": m.get("text"), "timestamp": parse_ts(m).isoformat(), "message_id": m.get("message_id")} for m in window_msgs
            ]
        }
        chunks.append(chunk)
    return chunks


def link_message_to_task(message, existing_tasks=None, history=None):
    """
    Link a message to a known task by fuzzy matching or context reference.
    existing_tasks: list of dicts with `task_id` and `title` (optional)
    history: list of prior messages
    Returns a list of matched task_ids
    """
    if existing_tasks is None:
        existing_tasks = []
    text = message.get("text", "").lower()
    linked = []

    # direct name match
    for t in existing_tasks:
        title = t.get("title", "").lower()
        if not title:
            continue
        if title in text or any(w in title for w in re.findall(r"\w+", text)) and sum(1 for w in re.findall(r"\w+", title) if w in text) >= 1:
            linked.append({"task_id": t.get("task_id"), "match_type": "direct", "task_title": t.get("title")})

    # pronoun/back-reference linking via history
    if not linked and history:
        # look backwards for explicit task mentions
        for prev in reversed(history[-20:]):
            pt = prev.get("text", "").lower()
            for t in existing_tasks:
                if t.get("title", "").lower() in pt:
                    linked.append({"task_id": t.get("task_id"), "match_type": "inferred_from_history", "task_title": t.get("title")})
                    break
            if linked:
                break

    return linked


def analyze_conversation(payload) -> dict:
    """
    Main analyzer API. Accepts payload with the shape specified in the task.
    Returns structured JSON with classification, entities, conversation_context, linked_tasks, confidence, reasoning.
    """
    # Validate payload
    messages = payload.get("last_n_messages", []) or []
    current_message = payload.get("current_message", "")
    workspace_id = payload.get("workspace_id")
    channel_id = payload.get("channel_id")
    user_id = payload.get("user_id")
    timestamp = payload.get("timestamp")
    existing_tasks = payload.get("existing_tasks", [])

    # Build conversation windows (include current message as last)
    history = list(messages)
    history.append({"user_id": user_id, "text": current_message, "timestamp": timestamp, "message_id": payload.get("message_id")})
    chunks = group_conversation(history, window=10)

    # Initialize extractor and classifier
    extractor = EntityExtractor()
    classifier = MessageClassifier()

    # Analyze per-window and for current message
    window_analysis = []
    confidences = []
    all_entities = []

    for chunk in chunks:
        combined_text = "\n".join([m["text"] for m in chunk["messages"]])
        cls = classifier.classify_all(combined_text)
        ent = extractor.extract_entities(combined_text)
        window_analysis.append({"chunk": chunk, "classification": cls, "entities": ent})
        # approximate confidence: take max intent score if present
        try:
            c = max([l["confidence"] for l in cls.get("intents", [])]) if cls.get("intents") else 0.0
        except Exception:
            c = 0.0
        confidences.append(float(c))
        all_entities.append(ent)

    # Analyze current message specifically
    current_cls = classifier.classify_all(current_message)
    current_ent = extractor.extract_entities(current_message)

    # Link current message to tasks
    linked = link_message_to_task({"text": current_message}, existing_tasks=existing_tasks, history=history)

    # Aggregate confidence
    overall_conf = float(sum(confidences) / len(confidences)) if confidences else 0.0

    reasoning_parts = []
    reasoning_parts.append(f"Processed {len(history)} messages in {len(chunks)} chunks.")
    if linked:
        reasoning_parts.append(f"Linked to {len(linked)} existing task(s).")
    else:
        reasoning_parts.append("No direct task link found; used context for inference.")

    result = {
        "classification": {"current": current_cls, "windows": window_analysis},
        "entities": {"current": current_ent, "windows": all_entities},
        "conversation_context": {"workspace_id": workspace_id, "channel_id": channel_id, "chunks": chunks},
        "linked_tasks": linked,
        "confidence": round(overall_conf, 4),
        "reasoning": " ".join(reasoning_parts)
    }

    return result

if __name__ == "__main__":
    # Quick test
    classifier = MessageClassifier()
    test_messages = [
        "Need to fix the bug in the headers by tonight",
        "The server is down, I can't do anything",
        "We might run out of budget if we continue this way",
        "I need the API key from the dev team before I can start",
        "Lunch sounds good!"
    ]
    
    for msg in test_messages:
        res = classifier.classify(msg)
        print(f"Message: {msg}")
        print(f"Result: {res}\n")
