"""Google Gemini summarizer (real, paid). Activated when a key is present and
DRY_RUN is off. Uses structured output (response_schema) so the model returns
the 7 fields as guaranteed JSON, with a tolerant parser as a backstop.
"""
from __future__ import annotations

import json
from typing import Optional

from .base import Summary, SUMMARY_FIELDS, SYSTEM_PROMPT, build_user_prompt


def _parse_json_object(raw: str) -> dict:
    """Parse the first JSON object in raw, tolerating leading/trailing junk
    (e.g. code fences, or a stray extra brace some models append)."""
    raw = raw.strip()
    # Strip a ```json ... ``` fence if present.
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw[: raw.rfind("```")]
    start = raw.find("{")
    if start == -1:
        raise ValueError(f"Gemini returned non-JSON summary: {raw[:200]!r}")
    # raw_decode reads one JSON value and ignores anything after it.
    obj, _ = json.JSONDecoder().raw_decode(raw[start:])
    if not isinstance(obj, dict):
        raise ValueError(f"Gemini returned non-object JSON: {type(obj).__name__}")
    return obj


# Per-request timeout scales with paper length: big papers make the model
# "think" longer, so they get more time; short ones still fail fast on a real
# stall. ~8s per 1000 chars, clamped to a sane floor/ceiling.
_MIN_TIMEOUT_S = 180.0     # floor — even a tiny paper waits at least this long
_MAX_TIMEOUT_S = 900.0     # ceiling — 15 min; beyond this treat as a genuine stall
_SECONDS_PER_1K_CHARS = 8.0


def timeout_for_text(text: str) -> float:
    """Adaptive per-request timeout (seconds) based on input length."""
    est = (len(text) / 1000.0) * _SECONDS_PER_1K_CHARS
    return max(_MIN_TIMEOUT_S, min(_MAX_TIMEOUT_S, est))


class GeminiSummarizer:
    def __init__(self, *, api_key: str, model: str):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for the Gemini summarizer")
        # Imported lazily so the package imports fine without the key/SDK.
        from google import genai  # type: ignore

        self._genai = genai
        # Client-level timeout is the hard ceiling; each request overrides it
        # with an adaptive value (see summarize). Without any timeout a stalled
        # connection blocks forever — this hung a run for 3.5h once.
        self._client = genai.Client(api_key=api_key)
        self.name = "google"
        self.model = model

    def _response_schema(self):
        from google.genai import types  # type: ignore

        return types.Schema(
            type=types.Type.OBJECT,
            properties={f: types.Schema(type=types.Type.STRING) for f in SUMMARY_FIELDS},
            required=list(SUMMARY_FIELDS),
            property_ordering=list(SUMMARY_FIELDS),
        )

    def summarize(self, *, title: str, venue: Optional[str], text: str) -> Summary:
        from google.genai import types  # type: ignore

        prompt = build_user_prompt(title=title, venue=venue, text=text)
        timeout_ms = int(timeout_for_text(text) * 1000)
        resp = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=self._response_schema(),
                temperature=0.2,
                http_options=types.HttpOptions(timeout=timeout_ms),
            ),
        )
        # Prefer the SDK's parsed object; fall back to tolerant text parsing.
        data = getattr(resp, "parsed", None)
        if not isinstance(data, dict):
            data = _parse_json_object(resp.text or "")
        return Summary.from_fields(data, provider=self.name, model=self.model)
