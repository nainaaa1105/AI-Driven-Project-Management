"""
chat.py — DEPRECATED
=====================
Chat message handling has been moved to messages.py which provides
workspace-aware, authenticated message endpoints.

This file is retained only for backward compatibility of the router import.
The actual POST /messages endpoint is now in app.api.messages.
"""

from fastapi import APIRouter

router = APIRouter(tags=["Chat (deprecated)"])

# All chat functionality is now handled by app.api.messages
