"""Factory: pick the summarizer from env, falling back to mock when it's safe.

Selection rule:
  - DRY_RUN on            -> mock (never spend money in a dry run)
  - provider key missing  -> mock (so the pipeline still runs end-to-end)
  - otherwise             -> the configured real provider
"""
from __future__ import annotations

from .. import config
from .base import Summarizer
from .mock import MockSummarizer, MockVerifier
from .verify import Verifier


def get_summarizer(*, force_real: bool = False) -> Summarizer:
    provider = (config.SUMMARIZER_PROVIDER or "").lower()

    if config.DRY_RUN and not force_real:
        return MockSummarizer()

    if provider == "google":
        if not config.GEMINI_API_KEY:
            print("[llm] GEMINI_API_KEY missing — using mock summarizer.")
            return MockSummarizer()
        from .gemini import GeminiSummarizer
        return GeminiSummarizer(api_key=config.GEMINI_API_KEY, model=config.SUMMARIZER_MODEL)

    if provider in ("mock", "", "none"):
        return MockSummarizer()

    print(f"[llm] unknown SUMMARIZER_PROVIDER={provider!r} — using mock.")
    return MockSummarizer()


def get_verifier(*, force_real: bool = False) -> Verifier:
    provider = (config.VERIFIER_PROVIDER or "").lower()

    if config.DRY_RUN and not force_real:
        return MockVerifier()

    if provider == "anthropic":
        if not config.ANTHROPIC_API_KEY:
            print("[llm] ANTHROPIC_API_KEY missing — using mock verifier.")
            return MockVerifier()
        from .claude import ClaudeVerifier
        return ClaudeVerifier(api_key=config.ANTHROPIC_API_KEY, model=config.VERIFIER_MODEL)

    if provider in ("mock", "", "none"):
        return MockVerifier()

    print(f"[llm] unknown VERIFIER_PROVIDER={provider!r} — using mock.")
    return MockVerifier()
