"""Retry transient provider errors with exponential backoff.

LLM endpoints briefly return 503 "overloaded / high demand", 429 rate-limits,
and other 5xx blips under load. Without a retry a single blip sinks a whole
publishing run — observed as two consecutive missed posts when Gemini returned
503 on the run's only summarize call. Non-transient errors propagate unchanged.
"""
from __future__ import annotations

import time
from typing import Callable, Optional, TypeVar

T = TypeVar("T")

# Substrings that mark a *transient* server-side condition worth retrying.
_TRANSIENT_MARKERS = (
    "503", "500", "502", "504", "429",
    "unavailable", "overloaded", "high demand", "rate limit",
    "try again", "timeout", "deadline", "temporarily",
)
_RETRY_CODES = {429, 500, 502, 503, 504}


def is_transient(e: Exception) -> bool:
    code = getattr(e, "status_code", None) or getattr(e, "code", None)
    if isinstance(code, int) and code in _RETRY_CODES:
        return True
    msg = str(e).lower()
    return any(m in msg for m in _TRANSIENT_MARKERS)


def with_retries(
    fn: Callable[[], T],
    *,
    what: str,
    attempts: int = 4,
    base_delay: float = 5.0,
    max_delay: float = 40.0,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call ``fn()``; on a transient error retry with exponential backoff
    (delays base_delay, 2×, 4× … capped at max_delay). A non-transient error,
    or exhausting all attempts, re-raises the last exception unchanged."""
    last: Optional[Exception] = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            if i == attempts - 1 or not is_transient(e):
                raise
            delay = min(max_delay, base_delay * (2 ** i))
            print(
                f"    [{what}] transient error ({type(e).__name__}: {str(e)[:70]}); "
                f"retry {i + 1}/{attempts - 1} in {delay:.0f}s",
                flush=True,
            )
            sleep(delay)
    assert last is not None  # unreachable — loop either returns or raises
    raise last
