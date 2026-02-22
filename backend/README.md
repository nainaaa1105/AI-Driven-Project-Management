# AI-Driven Project Intelligence - Backend

## Overview

FastAPI backend that orchestrates three ML modules to provide intelligent
project management:

| Module | Purpose | Key function |
|--------|---------|--------------|
| ML-1 (NLP) | Classify messages, extract entities | `MLProcessor.process_message(text)` |
| ML-2 (Task Similarity) | Detect duplicate / related tasks | `TaskSimilarityEngine.find_similar_tasks(text)` |
| ML-3 (Risk Prediction) | Predict project failure risk | `predict_risk(features, model, scaler, explainer)` |

## Database Setup

1. Create a PostgreSQL database named `ai_project_intelligence` (via pgAdmin or CLI).
2. Copy the env template and update credentials:
   ```bash
   cp .env.example .env
   # Edit .env with your actual POSTGRES_PASSWORD
   ```
3. Tables are created automatically on first startup via:
   ```python
   Base.metadata.create_all(bind=engine)
   ```

### Tables

| Table | Columns |
|-------|---------|
| `users` | id, name |
| `messages` | id, content, sender, ai_response, created_at |
| `tasks` | id, title, description, status, risk_score, risk_level, risk_reason, domain, urgency, similarity_label, linked_task_id, created_at |
| `alerts` | id, message, level, task_id, created_at |

## Installation

```bash
cd backend
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

## Running

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Or directly:
```bash
python -m app.main
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/messages` | Send a chat message → runs full ML pipeline |
| GET | `/tasks` | List all tasks (optional `?status=open`) |
| GET | `/tasks/{id}` | Get a single task |
| PATCH | `/tasks/{id}/status?new_status=resolved` | Update task status |
| POST | `/risk/predict` | Standalone risk prediction |
| GET | `/dashboard` | Aggregated dashboard stats |
| WS | `/ws/chat` | Real-time chat via WebSocket |
| GET | `/` | Health check |

### POST /messages — Example

```bash
curl -X POST http://localhost:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "Login is broken, waiting for backend API"}'
```

Response:
```json
{
  "summary": "Login",
  "task_created": true,
  "task_id": 1,
  "similarity_label": "NEW",
  "risk_score": 0.72,
  "risk_level": "High",
  "risk_reason": "Project is actively blocked; no progress can be made.",
  "alert": "⚠ High risk (High): Project is actively blocked.",
  "domain": "backend",
  "urgency": "high"
}
```

### POST /risk/predict — Example

```bash
curl -X POST http://localhost:8000/risk/predict \
  -H "Content-Type: application/json" \
  -d '{"task_complexity": 0.8, "dependency_count": 0.6, "sentiment_score": 0.3, "is_blocked": 1, "idle_time_days": 120}'
```

## ML Orchestration Flow

```
User message
    │
    ▼
ML-1: NLP ──► executive_report (summary, urgency, domain, sentiment)
    │
    ▼
ML-2: Task Similarity ──► DUPLICATE / RELATED / NEW
    │
    ▼
ML-3: Risk Prediction ──► risk_score, risk_level, SHAP explanation
    │
    ▼
DB: Save task + risk + alert (if score > 0.7)
    │
    ▼
Return JSON to frontend
```

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app, startup, CORS
│   ├── config.py            # .env loader
│   ├── database.py          # SQLAlchemy engine + session
│   ├── models/              # ORM models (users, messages, tasks, alerts)
│   ├── schemas/             # Pydantic request/response schemas
│   ├── services/            # AI orchestrator + CRUD helpers
│   ├── api/                 # REST endpoint routers
│   └── websocket/           # WebSocket chat handler
├── requirements.txt
├── .env.example
└── README.md
```
