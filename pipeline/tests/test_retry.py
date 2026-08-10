"""Retry-on-transient-error behavior for the LLM provider calls."""
from __future__ import annotations

import pytest

from pipeline.llm._retry import is_transient, with_retries


class _Boom(Exception):
    def __init__(self, msg, status_code=None):
        super().__init__(msg)
        self.status_code = status_code


def test_is_transient_by_message():
    assert is_transient(Exception("503 UNAVAILABLE: model is experiencing high demand"))
    assert is_transient(Exception("429 Too Many Requests"))
    assert is_transient(Exception("The model is overloaded, please try again"))
    assert not is_transient(Exception("400 invalid request: bad schema"))
    assert not is_transient(ValueError("Gemini returned non-JSON summary"))


def test_is_transient_by_status_code():
    assert is_transient(_Boom("nope", status_code=503))
    assert not is_transient(_Boom("nope", status_code=400))


def test_retries_then_succeeds():
    calls = {"n": 0}
    slept = []

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise Exception("503 high demand")
        return "ok"

    out = with_retries(flaky, what="test", base_delay=1.0, sleep=slept.append)
    assert out == "ok"
    assert calls["n"] == 3
    assert slept == [1.0, 2.0]  # backoff before the 2 retries


def test_nontransient_raises_immediately():
    calls = {"n": 0}

    def bad():
        calls["n"] += 1
        raise ValueError("bad schema")

    with pytest.raises(ValueError):
        with_retries(bad, what="test", sleep=lambda _: None)
    assert calls["n"] == 1  # no retries on a non-transient error


def test_gives_up_after_attempts():
    calls = {"n": 0}

    def always():
        calls["n"] += 1
        raise Exception("503 overloaded")

    with pytest.raises(Exception):
        with_retries(always, what="test", attempts=3, base_delay=1.0, sleep=lambda _: None)
    assert calls["n"] == 3  # exactly `attempts` tries, then re-raise
