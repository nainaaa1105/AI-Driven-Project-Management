# ML Engineer 2 — Task Similarity Engine

Part of **AI-Driven Project Intelligence for Engineering Teams**

## Responsibility

Before a new task is created from a chat message, this module acts as a **gatekeeper**:
- Prevents duplicate tasks from being created
- Links new tasks to related existing ones
- Passes similarity scores to ML Engineer 3's risk prediction model

## Approach — Hybrid Similarity

| Component | Method | Captures |
|---|---|---|
| TF-IDF + Cosine | Keyword overlap | Same technical terms, error codes |
| Sentence Transformer | Semantic embedding | Paraphrases, synonyms, intent |
| **Final Score** | `0.5 × TF-IDF + 0.5 × Semantic` | Both keyword and meaning |

**Model:** `all-MiniLM-L6-v2` (Hugging Face) — optimised for semantic similarity, CPU-friendly.

## Classification Thresholds

| Score | Label | Action |
|---|---|---|
| ≥ 0.80 | `DUPLICATE` | Block task creation |
| 0.50 – 0.79 | `RELATED` | Allow creation, link to existing task |
| < 0.50 | `NEW` | Allow creation freely |

Thresholds are centralised in [`thresholds.py`](thresholds.py) for easy tuning.

## File Structure

```
ml_2_task_similarity/
├── task_similarity.py   # TaskSimilarityEngine class (core logic)
├── thresholds.py        # All thresholds and model config
├── demo.py              # Runnable demo for judges
├── sample_tasks.json    # Sample existing tasks
└── README.md            # This file
```

## Input / Output

**Input** (from ML Engineer 1):
```python
new_task_text = "Authentication service is broken - users can't login"
```

**Output** (to backend / ML Engineer 3):
```python
[
  {
    "task_id": 1,
    "task_text": "Fix login authentication bug ...",
    "tfidf_similarity": 0.384,
    "semantic_similarity": 0.684,
    "final_similarity_score": 0.534,
    "label": "RELATED",
    "past_outcome": "success"
  }
]
```

## Run the Demo

```bash
cd ml/ml_2_task_similarity
python demo.py
```

## Integration with Other Modules

```
ML-1 (NLP extraction)
        ↓  plain text task
ML-2 (this module)
        ↓  similarity scores + label
ML-3 (risk scoring)
        ↓  risk score + SHAP explanation
Backend (FastAPI)
```

## Requirements

```
scikit-learn>=1.3.0
sentence-transformers>=2.2.2
numpy>=1.21.0
torch>=2.0.0
```
