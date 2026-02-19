# Horizon - AI Project Intelligence

An enterprise-grade, AI-powered project management system that transforms natural-language team conversations into structured tasks, risk predictions, and executive insights -- automatically.

---

## Architecture

```
backend/        FastAPI server, PostgreSQL, AI orchestration
frontend/       React 18 SPA (dark-theme, Horizon design system)
ml/             Three finalized ML modules (read-only)
  ml_1_nlp/       Zero-shot NLP classifier + entity extractor
  ml_2_task/      Semantic task similarity engine
  ml_3_risk/      Risk prediction model with SHAP explanations
```

## Key Capabilities

- **Chat-to-Task Pipeline** - send a message, get a structured task with domain, urgency, contacts, and risk score.
- **Duplicate & Dependency Detection** - ML-2 finds similar/related tasks via sentence embeddings.
- **Risk Prediction & Alerts** - ML-3 predicts failure probability with SHAP-based explanations.
- **Executive AI Summaries** - every message produces structured analysis visible in a sidebar panel.
- **Dashboard & Kanban Board** - real-time stats, risk distribution charts, and task management.

## ML Models (Finalized)

| Module | Model | Purpose |
|--------|-------|---------|
| ML-1 | `distilbert-base-uncased-mnli` + spaCy | Zero-shot classification, entity extraction |
| ML-2 | `all-MiniLM-L6-v2` | Sentence embeddings for task similarity |
| ML-3 | `RandomForestRegressor` + SHAP | Risk scoring with explainability |

> Models are loaded at runtime. No training step is required.

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL 14+

### 1. Clone & configure

```bash
git clone <repo-url>
cd AI-Driven-Project-Management

# Create environment file from template
cp .env.example backend/.env
# Edit backend/.env and set your POSTGRES_PASSWORD
```

### 2. Database

Create a PostgreSQL database:

```sql
CREATE DATABASE ai_project_intelligence;
```

Tables are auto-created on first backend startup via SQLAlchemy.

### 3. Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
python -m spacy download en_core_web_sm

uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`. Interactive docs at `/docs`.

### 4. Frontend

```bash
cd frontend
npm install
npm start
```

Opens at `http://localhost:3000`.

---

## Environment Variables

See [`.env.example`](.env.example) for all required variables. Copy it to `backend/.env` before running.

| Variable | Description |
|----------|-------------|
| `POSTGRES_DB` | Database name |
| `POSTGRES_USER` | Database user |
| `POSTGRES_PASSWORD` | Database password |
| `POSTGRES_HOST` | Database host |
| `POSTGRES_PORT` | Database port |
| `BACKEND_PORT` | FastAPI server port |
| `REACT_APP_API_URL` | Backend URL for the React app |

---

## Tech Stack

**Backend:** FastAPI, SQLAlchemy, psycopg2, python-dotenv
**Frontend:** React 18, Axios, CSS (Horizon design system)
**ML:** PyTorch, Transformers, sentence-transformers, scikit-learn, SHAP, spaCy, pandas

---

## License

This project is provided for educational and demonstration purposes.
