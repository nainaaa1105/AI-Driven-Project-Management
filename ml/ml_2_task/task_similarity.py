"""Task Similarity Engine — TF-IDF + Semantic, scoped by workspace/project."""

import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

import warnings
warnings.filterwarnings("ignore")

from thresholds import (
    TFIDF_WEIGHT, SEMANTIC_WEIGHT,
    TFIDF_MAX_FEATURES, TFIDF_NGRAM_RANGE, TFIDF_STOP_WORDS,
    SENTENCE_TRANSFORMER_MODEL, classify,
)


@dataclass
class Task:
    """Engineering task with workspace/project scope."""
    id: int
    title: str
    description: str
    past_outcome: str
    workspace_id: str
    project_id: Optional[str] = None
    assigned_user_id: Optional[str] = None

    def get_full_text(self) -> str:
        return f"{self.title} {self.description}"


class TaskSimilarityEngine:
    """Hybrid TF-IDF + Semantic similarity engine, scoped per workspace."""

    def __init__(self):
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=TFIDF_MAX_FEATURES,
            stop_words=TFIDF_STOP_WORDS,
            lowercase=True,
            ngram_range=TFIDF_NGRAM_RANGE,
        )
        print("Loading Sentence Transformer model...")
        self.semantic_model = SentenceTransformer(SENTENCE_TRANSFORMER_MODEL)

        self.existing_tasks: List[Task] = []
        self.tfidf_matrix = None
        self.semantic_embeddings = None

    def add_tasks(self, tasks: List[Task]) -> None:
        """Load tasks and precompute TF-IDF + semantic indices."""
        self.existing_tasks = tasks
        if not tasks:
            self.tfidf_matrix = None
            self.semantic_embeddings = None
            return

        task_texts = [t.get_full_text() for t in tasks]
        self.build_tfidf_index(task_texts)

        print("Computing semantic embeddings for existing tasks...")
        self.semantic_embeddings = self.semantic_model.encode(task_texts)
        print(f"Engine ready — {len(tasks)} tasks indexed.")

    def build_tfidf_index(self, task_texts: List[str]) -> None:
        """Fit TF-IDF vectorizer."""
        if not task_texts:
            self.tfidf_matrix = None
            return
        self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(task_texts)
        print(f"TF-IDF index built: {len(task_texts)} tasks, "
              f"{self.tfidf_matrix.shape[1]} features")

    def compute_tfidf_similarity(self, new_task_text: str) -> np.ndarray:
        """TF-IDF cosine similarity for keyword overlap."""
        if self.tfidf_matrix is None:
            return np.array([])
        vec = self.tfidf_vectorizer.transform([new_task_text])
        return cosine_similarity(vec, self.tfidf_matrix).flatten()

    def compute_semantic_similarity(self, new_task_text: str) -> np.ndarray:
        """Semantic cosine similarity via Sentence Transformer."""
        if self.semantic_embeddings is None or len(self.semantic_embeddings) == 0:
            return np.array([])
        embedding = self.semantic_model.encode([new_task_text])
        return cosine_similarity(embedding, self.semantic_embeddings).flatten()

    def find_similar_tasks(
        self, 
        new_task_text: str, 
        workspace_id: str,
        project_id: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Find similar tasks scoped to workspace/project.
        Returns: { decision, confidence, matched_task_id, assigned_user_id, similar_tasks }
        """
        # Scope comparison to the given workspace (and project if provided)
        scoped_tasks = [
            task for task in self.existing_tasks 
            if task.workspace_id == workspace_id and (
                project_id is None or task.project_id == project_id
            )
        ]
        
        if not scoped_tasks:
            assigned_user = self._determine_task_ownership(user_context) if user_context else None
            return {
                "decision": "create_new",
                "confidence": 0.0,
                "matched_task_id": None,
                "assigned_user_id": assigned_user,
                "similar_tasks": []
            }

        scoped_task_texts = [task.get_full_text() for task in scoped_tasks]

        if scoped_task_texts:
            scoped_tfidf_matrix = self.tfidf_vectorizer.fit_transform(scoped_task_texts)
            vec = self.tfidf_vectorizer.transform([new_task_text])
            tfidf_scores = cosine_similarity(vec, scoped_tfidf_matrix).flatten()
        else:
            tfidf_scores = np.array([])

        if scoped_task_texts:
            scoped_embeddings = self.semantic_model.encode(scoped_task_texts)
            new_embedding = self.semantic_model.encode([new_task_text])
            semantic_scores = cosine_similarity(new_embedding, scoped_embeddings).flatten()
        else:
            semantic_scores = np.array([])

        n = len(scoped_tasks)
        if len(tfidf_scores) == 0:
            tfidf_scores = np.zeros(n)
        if len(semantic_scores) == 0:
            semantic_scores = np.zeros(n)

        final_scores = TFIDF_WEIGHT * tfidf_scores + SEMANTIC_WEIGHT * semantic_scores

        min_threshold = 0.3
        similar_tasks = []
        for i, task in enumerate(scoped_tasks):
            score = float(final_scores[i])
            if score >= min_threshold:
                similar_tasks.append({
                    "task_id": task.id,
                    "task_text": task.get_full_text(),
                    "tfidf_similarity": float(tfidf_scores[i]) if len(tfidf_scores) > i else 0.0,
                    "semantic_similarity": float(semantic_scores[i]) if len(semantic_scores) > i else 0.0,
                    "final_similarity_score": score,
                    "past_outcome": task.past_outcome,
                    "assigned_user_id": task.assigned_user_id
                })

        similar_tasks.sort(key=lambda x: x["final_similarity_score"], reverse=True)

        best_match = similar_tasks[0] if similar_tasks else None
        assigned_user = self._determine_task_ownership(user_context) if user_context else None
        
        if not best_match:
            return {
                "decision": "create_new",
                "confidence": 0.0,
                "matched_task_id": None,
                "assigned_user_id": assigned_user,
                "similar_tasks": []
            }
        
        confidence = best_match["final_similarity_score"]

        # >= 0.85 → auto_link | 0.65–0.85 → suggest | < 0.65 → create_new
        if confidence >= 0.85:
            return {
                "decision": "auto_link",
                "confidence": confidence,
                "matched_task_id": best_match["task_id"],
                "assigned_user_id": assigned_user,
                "similar_tasks": similar_tasks
            }
        
        elif confidence >= 0.65:
            return {
                "decision": "suggest",
                "confidence": confidence,
                "matched_task_id": best_match["task_id"],
                "assigned_user_id": assigned_user,
                "similar_tasks": similar_tasks
            }
        
        else:
            return {
                "decision": "create_new",
                "confidence": confidence,
                "matched_task_id": None,
                "assigned_user_id": assigned_user,
                "similar_tasks": similar_tasks
            }

    def _determine_task_ownership(self, user_context: Dict[str, Any]) -> Optional[str]:
        """
        Rule-based ownership: 1 mention → that user | 0 mentions → sender | multiple → None.
        """
        if not user_context:
            return None
            
        mentioned_users = user_context.get("mentioned_users", [])
        sender_id = user_context.get("sender_id")

        if len(mentioned_users) == 1:
            return mentioned_users[0]
        elif len(mentioned_users) == 0 and sender_id:
            return sender_id
        else:
            return None
