"""
Task Similarity Engine — ML Engineer 2
AI-Driven Project Intelligence for Engineering Teams (Hackathon)

Hybrid approach:
  - TF-IDF + Cosine Similarity  →  keyword overlap
  - Sentence Transformers        →  semantic meaning
  - Final score = 0.5 * tfidf + 0.5 * semantic
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Any

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
    """Represents a single engineering task."""
    id: int
    title: str
    description: str
    past_outcome: str  # "success" | "delayed"

    def get_full_text(self) -> str:
        """Combine title + description for similarity analysis."""
        return f"{self.title} {self.description}"


class TaskSimilarityEngine:
    """
    Hybrid Task Similarity Engine.

    Usage:
        engine = TaskSimilarityEngine()
        engine.add_tasks(existing_tasks)
        results = engine.find_similar_tasks("Authentication is broken")
    """

    def __init__(self):
        # TF-IDF for fast keyword overlap detection
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=TFIDF_MAX_FEATURES,
            stop_words=TFIDF_STOP_WORDS,
            lowercase=True,
            ngram_range=TFIDF_NGRAM_RANGE,
        )

        # Sentence Transformer for deep semantic similarity
        print("Loading Sentence Transformer model...")
        self.semantic_model = SentenceTransformer(SENTENCE_TRANSFORMER_MODEL)

        self.existing_tasks: List[Task] = []
        self.tfidf_matrix = None
        self.semantic_embeddings = None

    # ──────────────────────────────────────────────────────────────────────────
    # Index building
    # ──────────────────────────────────────────────────────────────────────────

    def add_tasks(self, tasks: List[Task]) -> None:
        """
        Load existing tasks and precompute all indices.
        Call once at startup; call again whenever tasks change.
        """
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
        """Fit TF-IDF vectorizer and store the document matrix."""
        if not task_texts:
            self.tfidf_matrix = None
            return
        self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(task_texts)
        print(f"TF-IDF index built: {len(task_texts)} tasks, "
              f"{self.tfidf_matrix.shape[1]} features")

    # ──────────────────────────────────────────────────────────────────────────
    # Similarity computation
    # ──────────────────────────────────────────────────────────────────────────

    def compute_tfidf_similarity(self, new_task_text: str) -> np.ndarray:
        """
        Keyword overlap via TF-IDF cosine similarity.
        Good for: same technical terms, acronyms, error codes.
        """
        if self.tfidf_matrix is None:
            return np.array([])
        vec = self.tfidf_vectorizer.transform([new_task_text])
        return cosine_similarity(vec, self.tfidf_matrix).flatten()

    def compute_semantic_similarity(self, new_task_text: str) -> np.ndarray:
        """
        Meaning overlap via Sentence Transformer cosine similarity.
        Good for: paraphrases, synonyms, conceptually identical tasks.
        """
        if self.semantic_embeddings is None or len(self.semantic_embeddings) == 0:
            return np.array([])
        embedding = self.semantic_model.encode([new_task_text])
        return cosine_similarity(embedding, self.semantic_embeddings).flatten()

    # ──────────────────────────────────────────────────────────────────────────
    # Main API
    # ──────────────────────────────────────────────────────────────────────────

    def find_similar_tasks(
        self, new_task_text: str, threshold: float = 0.50
    ) -> List[Dict[str, Any]]:
        """
        Find tasks similar to new_task_text.

        Args:
            new_task_text: Plain-text task extracted from a chat message.
            threshold:     Minimum final score to include in results.

        Returns:
            List of dicts sorted by final_similarity_score descending:
            {
              "task_id": int,
              "task_text": str,
              "tfidf_similarity": float,
              "semantic_similarity": float,
              "final_similarity_score": float,
              "label": "DUPLICATE" | "RELATED" | "NEW",
              "past_outcome": str
            }
        """
        if not self.existing_tasks:
            return []

        tfidf_scores = self.compute_tfidf_similarity(new_task_text)
        semantic_scores = self.compute_semantic_similarity(new_task_text)

        # Fall back to zeros if a component is unavailable
        n = len(self.existing_tasks)
        if len(tfidf_scores) == 0:
            tfidf_scores = np.zeros(n)
        if len(semantic_scores) == 0:
            semantic_scores = np.zeros(n)

        final_scores = TFIDF_WEIGHT * tfidf_scores + SEMANTIC_WEIGHT * semantic_scores

        results = []
        for i, task in enumerate(self.existing_tasks):
            score = float(final_scores[i])
            if score >= threshold:
                results.append({
                    "task_id": task.id,
                    "task_text": task.get_full_text(),
                    "tfidf_similarity": float(tfidf_scores[i]),
                    "semantic_similarity": float(semantic_scores[i]),
                    "final_similarity_score": score,
                    "label": classify(score),
                    "past_outcome": task.past_outcome,
                })

        results.sort(key=lambda x: x["final_similarity_score"], reverse=True)
        return results
