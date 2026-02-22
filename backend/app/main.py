"""
main.py
=======
FastAPI application entry-point.

Startup sequence:
  1. Create all DB tables via SQLAlchemy metadata
  2. Seed the AI Bot system user
  3. Initialise the AI Orchestrator (loads ML-1, ML-2, ML-3 models)
  4. Register API routers and WebSocket handler
  5. Enable CORS for the React frontend
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

from app.database import engine, Base, SessionLocal
from app.config import settings
# Register all models so Base.metadata knows about them
from app.models import (  # noqa: F401
    User, Message, Task, Alert, CustomDomain,
    Workspace, WorkspaceMember, Channel, MessageTaskMap, AIEvent,
)
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.messages import router as messages_router
from app.api.tasks import router as tasks_router
from app.api.risk import router as risk_router
from app.api.dashboard import router as dashboard_router
from app.api.workspaces import router as workspaces_router
from app.api.channels import router as channels_router
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
        "Multi-user, workspace-based backend that orchestrates NLP classification (ML-1), "
        "task similarity detection (ML-2), and risk prediction (ML-3) "
        "to provide intelligent, real-time project management."
    ),
    version="2.0.0",
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
# Auth (unprotected)
app.include_router(auth_router)
# Protected APIs
app.include_router(messages_router)
app.include_router(tasks_router)
app.include_router(risk_router)
app.include_router(dashboard_router)
app.include_router(workspaces_router)
app.include_router(channels_router)
# Deprecated (kept for backward compat, no active routes)
app.include_router(chat_router)
# WebSocket
app.include_router(ws_router)


# ── Startup event ────────────────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    """Create DB tables, seed AI bot, and pre-load ML models."""
    logger.info("Creating database tables …")
    Base.metadata.create_all(bind=engine)
    logger.info("Tables ready.")

    # Seed AI Bot user
    _seed_ai_bot()

    logger.info("Initialising AI Orchestrator …")
    from app.services.ai_orchestrator import orchestrator
    orchestrator.initialise()
    logger.info("Startup complete — server is ready.")


def _seed_ai_bot():
    """
    Create the AI Bot system user if it doesn't exist.
    The bot is used to post automated messages into channels.
    """
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == settings.AI_BOT_EMAIL).first()
        if not existing:
            bot = User(
                name=settings.AI_BOT_NAME,
                email=settings.AI_BOT_EMAIL,
                password_hash=None,  # System user, cannot log in
                role="system",
            )
            db.add(bot)
            db.commit()
            logger.info(f"AI Bot user seeded (email={settings.AI_BOT_EMAIL})")
        else:
            logger.info(f"AI Bot user already exists (id={existing.id})")
    finally:
        db.close()


# ── Health-check ─────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    """Health-check endpoint."""
    return {"status": "ok", "service": "AI-Driven Project Intelligence", "version": "2.0.0"}


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
