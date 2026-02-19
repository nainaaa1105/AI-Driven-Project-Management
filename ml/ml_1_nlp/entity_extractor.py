import spacy
import re
from datetime import datetime, timedelta

class EntityExtractor:
    def __init__(self):
        # Load spaCy model
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            # Fallback message handled in README/instructions
            print("Warning: spaCy model 'en_core_web_sm' not found. Please run 'python -m spacy download en_core_web_sm'")
            self.nlp = None

        # Regex for common time mentions
        self.time_regex = [
            r"\b(\d+)\s*(days?|weeks?|months?|hours?|mins?|minutes?)\b", 
            r"\b(today|tomorrow|yesterday|tonight)\b",           
            r"\b(next|this)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            r"\b(by|on)\s+(\d{1,2}/\d{1,2}(/\d{2,4})?)\b",
            r"\b(asap|eod|end of day|end of the week)\b",
        ]

    def extract_entities(self, text):
        entities = {
            "task_name": None,
            "dependency_reference": [],
            "time_mentions": [],
            "reason_or_context": None,
            "sentiment": "neutral",
            "actors": [],
            "tools_and_tech": [],
            "urgency": "normal",
            "contact_info": {"emails": [], "urls": []},
            "action_items": []
        }

    def extract_entities(self, text):
        entities = self._get_initial_entities()

        if self.nlp:
            doc = self.nlp(text)
            text_lower = text.lower()
            
            # 1. Extract Actors (Who acted on it)
            for ent in doc.ents:
                if ent.label_ in ["PERSON", "ORG"]:
                    if ent.text not in entities["actors"]:
                        entities["actors"].append(ent.text)
            
            # 2. Tech & Tools Extraction
            tech_keywords = ["python", "javascript", "react", "vue", "aws", "docker", "kubernetes", "sql", "nosql", "git", "api", "rest", "graphql", "css", "html"]
            for token in doc:
                if token.text.lower() in tech_keywords:
                    if token.text not in entities["tools_and_tech"]:
                        entities["tools_and_tech"].append(token.text)

            # 3. Urgency Detection
            urgent_words = ["urgent", "asap", "emergency", "immediately", "blocker", "critical", "high priority"]
            for word in urgent_words:
                if word in text_lower:
                    entities["urgency"] = "high"
                    break

            # 4. Contact Info (Emails & URLs)
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            url_pattern = r'https?://[^\s/$.?#].[^\s]*'
            entities["contact_info"]["emails"] = re.findall(email_pattern, text)
            entities["contact_info"]["urls"] = re.findall(url_pattern, text)

            # 5. Extraction of Time Mentions
            for ent in doc.ents:
                if ent.label_ in ["DATE", "TIME"]:
                    if ent.text not in entities["time_mentions"]:
                        entities["time_mentions"].append(ent.text)

            # 6. Task Name & Action Items
            action_verbs = ["fix", "update", "create", "finish", "complete", "implement", "build", "refactor", "do", "make", "achieved", "deploy", "review"]
            for token in doc:
                if token.lemma_.lower() in action_verbs and token.pos_ in ["VERB", "ADJ"]:
                    # Task Name
                    descendants = [child for child in token.children if child.dep_ in ["dobj", "attr", "prep", "acomp"]]
                    if descendants and not entities["task_name"]:
                        obj = descendants[0]
                        task_text = " ".join([t.text for t in obj.subtree])
                        entities["task_name"] = f"{token.text} {task_text}".strip()
                    
                    # Action Item (The whole verb phrase)
                    action_phrase = " ".join([t.text for t in token.subtree])
                    if action_phrase not in entities["action_items"]:
                        entities["action_items"].append(action_phrase)

            # 7. Reason or Why
            reason_found = False
            for token in doc:
                if token.text.lower() in ["because", "since", "as"] and token.dep_ == "mark":
                    reason_clause = " ".join([t.text for t in token.head.subtree])
                    entities["reason_or_context"] = reason_clause
                    reason_found = True
                    break
            
            if not reason_found:
                for connector in ["due to", "so that", "leading to", "resulting in", "stuck on", "because of"]:
                    if connector in text_lower:
                        parts = text.split(connector, 1)
                        if len(parts) > 1:
                            entities["reason_or_context"] = parts[1].strip()
                            break

            # 8. Sentiment
            positive_words = ["done", "achieved", "success", "great", "finished", "working", "fixed", "yay", "happy", "completed"]
            negative_words = ["broken", "failed", "stuck", "blocker", "risk", "missing", "delay", "error", "problem", "issue"]
            pos_score = sum(1 for w in positive_words if w in text_lower)
            neg_score = sum(1 for w in negative_words if w in text_lower)
            if pos_score > neg_score: entities["sentiment"] = "positive"
            elif neg_score > pos_score: entities["sentiment"] = "negative"

        # Regex Time fallback
        for pattern in self.time_regex:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                time_str = match.group(0)
                if time_str.lower() not in [t.lower() for t in entities["time_mentions"]]:
                    entities["time_mentions"].append(time_str)

        return entities

    def _get_initial_entities(self):
        return {
            "task_name": None,
            "dependency_reference": [],
            "time_mentions": [],
            "reason_or_context": None,
            "sentiment": "neutral",
            "actors": [],
            "tools_and_tech": [],
            "urgency": "normal",
            "contact_info": {"emails": [], "urls": []},
            "action_items": []
        }

if __name__ == "__main__":
    extractor = EntityExtractor()
    test_messages = [
        "Finish the documentation by tomorrow",
        "Wait for the API key from the dev team",
        "The project will take 2 weeks to complete",
        "I need to fix the login page after the auth module is done"
    ]

    for msg in test_messages:
        print(f"Message: {msg}")
        print(f"Entities: {extractor.extract_entities(msg)}\n")
