"""Swappable LLM layer: summarize() (Phase 1) and verify() (Phase 2).

Callers use get_summarizer()/get_verifier() and never import a concrete provider,
so the model/provider can change via env without touching the pipeline.
"""
from .base import Summary, SUMMARY_FIELDS
from .verify import Verdict, passes_gate
from .prescreen import ScreenDecision
from .provider import get_summarizer, get_verifier, get_prescreener

__all__ = [
    "Summary", "SUMMARY_FIELDS", "get_summarizer",
    "Verdict", "passes_gate", "get_verifier",
    "ScreenDecision", "get_prescreener",
]
