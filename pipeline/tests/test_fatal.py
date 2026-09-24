"""Infrastructure failures must be told apart from content-level flags/skips."""
from pipeline.run import _is_fatal


class _Err(Exception):
    def __init__(self, msg, status_code=None):
        super().__init__(msg)
        self.status_code = status_code


def test_billing_and_auth_are_fatal():
    assert _is_fatal(Exception("Your credit balance is too low to access the Anthropic API"))
    assert _is_fatal(Exception("invalid x-api-key"))
    assert _is_fatal(Exception("authentication_error"))
    assert _is_fatal(_Err("nope", status_code=401))
    assert _is_fatal(_Err("nope", status_code=402))
    assert _is_fatal(_Err("nope", status_code=403))


def test_content_and_transient_are_not_fatal():
    assert not _is_fatal(Exception("503 the model is overloaded"))
    assert not _is_fatal(Exception("Gemini returned non-JSON summary"))
    assert not _is_fatal(_Err("bad", status_code=503))
    assert not _is_fatal(_Err("bad", status_code=400))  # generic 400 is not, by itself, fatal
