"""Anthropic Claude verifier (real, paid). Deliberately a different family from
the Gemini summarizer so it doesn't share the summarizer's blind spots (spec §6).

Activated when an Anthropic key is present and DRY_RUN is off.
"""
from __future__ import annotations

from typing import Optional

from .base import Summary
from .verify import Verdict, SYSTEM_PROMPT_VERIFY, build_verify_prompt
from .gemini import _parse_json_object, timeout_for_text  # reuse tolerant parse + adaptive timeout


class ClaudeVerifier:
    def __init__(self, *, api_key: str, model: str):
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for the Claude verifier")
        import anthropic  # type: ignore

        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self.name = "anthropic"
        self.model = model

    def verify(self, *, title: str, source_text: str, summary: Summary) -> Verdict:
        prompt = build_verify_prompt(title=title, source_text=source_text, summary=summary)
        timeout_s = timeout_for_text(source_text)
        # Opus 4.8 rejects temperature; leave sampling params off. Small output.
        resp = self._client.with_options(timeout=timeout_s).messages.create(
            model=self.model,
            max_tokens=2000,
            system=SYSTEM_PROMPT_VERIFY,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            b.text for b in resp.content if getattr(b, "type", None) == "text"
        )
        if resp.stop_reason == "refusal":
            # Treat a safety refusal as a flag for human review, never an auto-pass.
            return Verdict(
                verdict="flag", score=0.0, confidence=0.0,
                unsupported_claims=[], notes="verifier refused — sent to review queue",
                provider=self.name, model=self.model,
            )
        data = _parse_json_object(text)
        return Verdict.from_fields(data, provider=self.name, model=self.model)
