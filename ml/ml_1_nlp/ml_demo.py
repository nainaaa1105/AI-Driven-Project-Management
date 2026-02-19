from ml.nlp_classifier import MessageClassifier
from ml.entity_extractor import EntityExtractor

class MLProcessor:
    def __init__(self):
        print("Initializing NLP Models...")
        self.classifier = MessageClassifier()
        self.extractor = EntityExtractor()
        print("Models loaded successfully.")

    def process_message(self, text):
        """
        Main API-ready function to process a message.
        """
        classification = self.classifier.classify_all(text)
        entities = self.extractor.extract_entities(text)
        
        # Synthesize the executive report
        report = self._generate_executive_report(text, classification, entities)
        
        return {
            "original_text": text,
            "executive_report": report,
            "technical_details": {
                "intents": [c['label'] for c in classification['intents']],
                "event_types": [c['label'] for c in classification['event_types']],
                "domains": [c['label'] for c in classification['domains']],
                "sentiment": entities["sentiment"],
                "raw_entities": entities
            }
        }

    def _generate_executive_report(self, text, classification, entities):
        """
        Synthesizes specific answers for the user: What, Who, Domain, Why (if pending), When/Who (future).
        """
        intents = [c['label'] for c in classification['intents']]
        domains = [c['label'] for c in classification['domains']]
        
        # 1. What was the issue/achievement?
        achievement_or_issue = entities["task_name"] or "General update/discussion"
        
        # 2. Who solved it / Who is acting?
        actors = entities["actors"]
        is_solved = any(word in text.lower() for word in ["solved", "fixed", "finished", "completed", "done", "achieved"])
        
        who_solved = actors if is_solved else "Not yet solved"
        
        # 3. Domain
        domain_str = ", ".join(domains) if domains else "General"
        
        # 4. If not solved, Why?
        if not is_solved:
            why_not = entities["reason_or_context"] or "No specific reason provided"
        else:
            why_not = "N/A (Resolved)"

        # 5. When will it be solved?
        when_will_it_be_solved = entities["time_mentions"] if not is_solved or any(t in text.lower() for t in ["tomorrow", "next", "by"]) else "Already resolved"
        if not when_will_it_be_solved and not is_solved:
            when_will_it_be_solved = "Unscheduled"
            
        # 6. Who will solve it?
        # Logic: If not solved, look for names. If "I will", it's the sender.
        who_will_solve = actors if not is_solved else "N/A"

        return {
            "summary": achievement_or_issue,
            "status": "Resolved" if is_solved else "Pending/Active",
            "urgency": entities["urgency"],
            "who_acted_or_solved": who_solved,
            "domain": domain_str,
            "tech_stack": entities["tools_and_tech"],
            "why_pending": why_not,
            "resolution_plan": {
                "when": when_will_it_be_solved,
                "target_actor": who_will_solve,
                "suggested_actions": entities["action_items"]
            },
            "contacts_found": entities["contact_info"]
        }

if __name__ == "__main__":
    processor = MLProcessor()
    
    print("\n" + "="*50)
    print("NLP CLI Tool - Type 'exit' or 'quit' to stop")
    print("="*50)

    while True:
        try:
            print("\n" + "-"*30)
            sample_text = input("Enter a message to analyze: ").strip()
            
            if not sample_text:
                continue
            if sample_text.lower() in ['exit', 'quit']:
                break
                
            results = processor.process_message(sample_text)
            
            print("\nAnalysis Results:")
            import json
            print(json.dumps(results, indent=2))
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")

    print("\nGoodbye!")
