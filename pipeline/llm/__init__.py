"""Swappable LLM layer: summarize() now, verify() in Phase 2.

Callers use get_summarizer() and never import a concrete provider, so the
model/provider can change via env without touching the pipeline.
"""
from .base import Summary, SUMMARY_FIELDS
from .provider import get_summarizer

__all__ = ["Summary", "SUMMARY_FIELDS", "get_summarizer"]
