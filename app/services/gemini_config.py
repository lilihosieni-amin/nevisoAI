"""
Gemini API configuration for RAG Chat

This module configures Gemini to use the direct API for chat functionality.
Uses the same API key as the transcription service.

NOTE: We always reconfigure because some libraries (like sentence-transformers)
can interfere with the HTTP client settings.
"""
import google.generativeai as genai
from app.core.config import settings


def configure_gemini():
    """
    Configure Gemini API for RAG Chat using direct API key

    Always reconfigures to ensure settings are applied correctly
    (some libraries like sentence-transformers can interfere)
    """
    genai.configure(api_key=settings.GEMINI_API_KEY)
