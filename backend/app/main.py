"""
main.py
=======
FastAPI application entry-point.

Startup sequence:
  1. Create all DB tables via SQLAlchemy metadata
  2. Initialise the AI Orchestrator (loads ML-1, ML-2, ML-3 models)
  3. Register API routers and WebSocket handler
  4. Enable CORS for the React frontend
"""

import logging
import sys
import os

# Ensure the project root is on sys.path so ML modules can be discovered
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Ensure backend/ is on sys.path for `app.*` imports
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.models import User, Message, Task, Alert, CustomDomain  # noqa: F401 — register models
from app.api.chat import router as chat_router
from app.api.tasks import router as tasks_router
from app.api.risk import router as risk_router
from app.api.dashboard import router as dashboard_router
from app.websocket.chat_socket import router as ws_router

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-20s  %(levelname)-7s  %(message)s",
)
logger = logging.getLogger("main")

# ── FastAPI app ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI-Driven Project Intelligence",
    description=(
        "Backend that orchestrates NLP classification (ML-1), "
        "task similarity detection (ML-2), and risk prediction (ML-3) "
        "to provide intelligent project management."
    ),
    version="1.0.0",
)

# ── CORS — allow the React dev server ────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ────────────────────────────────────────────────────────
app.include_router(chat_router)
app.include_router(tasks_router)
app.include_router(risk_router)
app.include_router(dashboard_router)
app.include_router(ws_router)


# ── Startup event ────────────────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    """Create DB tables and pre-load ML models."""
    logger.info("Creating database tables …")
    Base.metadata.create_all(bind=engine)
    logger.info("Tables ready.")

    logger.info("Initialising AI Orchestrator …")
    from app.services.ai_orchestrator import orchestrator
    orchestrator.initialise()
    logger.info("Startup complete — server is ready.")


# ── Health-check ─────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    """Health-check endpoint."""
    return {"status": "ok", "service": "AI-Driven Project Intelligence"}


# ── Run with uvicorn when executed directly ──────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    from app.config import settings

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.BACKEND_PORT,
        reload=True,
    )
