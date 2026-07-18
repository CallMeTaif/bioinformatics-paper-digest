"""Verifier verdict parsing + publish gate (the accuracy-critical logic, §6)."""
from pipeline.llm.verify import Verdict, passes_gate


def test_gate_passes_high_confidence_clean_pass():
    v = Verdict(verdict="pass", score=0.9, confidence=0.9, unsupported_claims=[])
    assert passes_gate(v, threshold=0.8) is True


def test_gate_flags_low_score():
    v = Verdict(verdict="pass", score=0.6, confidence=0.9)
    assert passes_gate(v, threshold=0.8) is False


def test_gate_flags_low_confidence():
    v = Verdict(verdict="pass", score=0.9, confidence=0.5)
    assert passes_gate(v, threshold=0.8) is False


def test_gate_flags_explicit_flag_verdict():
    v = Verdict(verdict="flag", score=0.95, confidence=0.95)
    assert passes_gate(v, threshold=0.8) is False


def test_gate_publishes_pass_despite_informational_claim():
    # A genuine hallucination is encoded as verdict='flag' by the verifier; the
    # claims list is informational, so a high-confidence 'pass' with a minor
    # listed note still auto-publishes (avoids over-flagging defensible paraphrases).
    v = Verdict(verdict="pass", score=0.9, confidence=0.9,
                unsupported_claims=["minor defensible paraphrase note"])
    assert passes_gate(v, threshold=0.8) is True


def test_from_fields_clamps_and_defaults():
    v = Verdict.from_fields(
        {"verdict": "PASS", "score": 1.5, "confidence": -0.2,
         "unsupported_claims": "single string", "notes": "ok"},
        provider="anthropic", model="claude-opus-4-8",
    )
    assert v.verdict == "pass"
    assert v.score == 1.0            # clamped to [0,1]
    assert v.confidence == 0.0       # clamped
    assert v.unsupported_claims == ["single string"]  # coerced to list


def test_from_fields_unknown_verdict_becomes_flag():
    v = Verdict.from_fields({"verdict": "maybe", "score": 0.9, "confidence": 0.9},
                            provider="x", model="y")
    assert v.verdict == "flag"       # unknown verdicts fail safe


def test_mock_verifier_passes():
    from pipeline.llm.mock import MockVerifier
    from pipeline.llm.base import Summary
    v = MockVerifier().verify(title="t", source_text="body", summary=Summary(tldr="x"))
    assert v.verdict == "pass" and v.provider == "mock"
    assert passes_gate(v, threshold=0.8) is True
