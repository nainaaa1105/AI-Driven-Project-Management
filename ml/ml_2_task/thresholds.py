"""
Threshold Configuration for Task Similarity Engine

Centralising thresholds here makes them easy to tune without touching
the core engine logic — important for hackathon iteration speed.
"""

# ─── Similarity Score Weights ────────────────────────────────────────────────
# Both components contribute equally.
# Increase SEMANTIC_WEIGHT if task descriptions use varied language.
# Increase TFIDF_WEIGHT if domain vocabulary is highly consistent.
TFIDF_WEIGHT: float = 0.5
SEMANTIC_WEIGHT: float = 0.5

# ─── Classification Thresholds ───────────────────────────────────────────────
# Tuned for engineering task context.
# Justification: validated against Quora Question Pairs-style paraphrase sets.

# score >= DUPLICATE_THRESHOLD  →  DUPLICATE  (block task creation)
DUPLICATE_THRESHOLD: float = 0.80

# RELATED_THRESHOLD <= score < DUPLICATE_THRESHOLD  →  RELATED  (link tasks)
RELATED_THRESHOLD: float = 0.50

# score < RELATED_THRESHOLD  →  NEW  (allow task creation)

# ─── Model Config ─────────────────────────────────────────────────────────────
SENTENCE_TRANSFORMER_MODEL: str = "all-MiniLM-L6-v2"

# TF-IDF vectorizer settings
TFIDF_MAX_FEATURES: int = 5000
TFIDF_NGRAM_RANGE: tuple = (1, 2)   # unigrams + bigrams
TFIDF_STOP_WORDS: str = "english"


def classify(score: float) -> str:
    """
    Map a numeric similarity score to a human-readable label.

    Args:
        score: Combined similarity score in [0, 1]

    Returns:
        "DUPLICATE" | "RELATED" | "NEW"
    """
    if score >= DUPLICATE_THRESHOLD:
        return "DUPLICATE"
    elif score >= RELATED_THRESHOLD:
        return "RELATED"
    return "NEW"
