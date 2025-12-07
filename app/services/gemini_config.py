"""
Gemini API configuration for RAG Chat (via Dispatcher)

This module configures Gemini to use the dispatcher for chat functionality.
The dispatcher provides load balancing and rate limit management.

NOTE: We always reconfigure because some libraries (like sentence-transformers)
can interfere with the HTTP client settings.
"""
import google.generativeai as genai
from app.core.config import settings


def configure_gemini():
    """
    Configure Gemini API for RAG Chat via Dispatcher

    Always reconfigures to ensure settings are applied correctly
    (some libraries like sentence-transformers can interfere)
    """
    genai.configure(
        api_key=settings.GEMINI_DISPATCHER_POOL,  # Pool name (e.g., "social")
        transport='rest',  # Required for dispatcher
        client_options={"api_endpoint": settings.GEMINI_DISPATCHER_URL}
    )
