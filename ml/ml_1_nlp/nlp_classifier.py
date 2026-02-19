import torch
from transformers import pipeline

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
