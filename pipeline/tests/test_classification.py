"""Model-provided topic/difficulty, with fallback to the keyword heuristic."""
from pipeline.llm.base import Summary
from pipeline.sources.base import Paper
from pipeline.publish.record import build_record
from pipeline.topics import CANONICAL_TAGS, accent_for_tag, is_canonical_tag


def test_canonical_vocabulary_is_nonempty_and_has_accents():
    assert "bioinformatics" in CANONICAL_TAGS
    for tag in CANONICAL_TAGS:
        assert accent_for_tag(tag) in {"A", "C", "G", "T"}


def test_from_fields_accepts_valid_classification():
    s = Summary.from_fields(
        {"tldr": "x", "topic": "proteomics", "difficulty": "advanced"},
        provider="google", model="m",
    )
    assert s.topic == "proteomics" and s.difficulty == "advanced"


def test_from_fields_rejects_invented_topic():
    s = Summary.from_fields(
        {"tldr": "x", "topic": "astrophysics", "difficulty": "extreme"},
        provider="google", model="m",
    )
    assert s.topic == "" and s.difficulty == ""   # dropped -> caller falls back


def test_record_prefers_model_classification():
    paper = Paper(title="A paper about single-cell RNA-seq", abstract="single-cell")
    summary = Summary(tldr="t", topic="drug-discovery", difficulty="intro")
    rec = build_record(paper, summary)
    # model said drug-discovery even though keywords scream single-cell
    assert rec["subfield_tags"] == ["drug-discovery"]
    assert rec["difficulty_level"] == "intro"
    assert rec["tag_accent"] == accent_for_tag("drug-discovery")


def test_record_falls_back_to_keywords_when_model_silent():
    paper = Paper(title="A single-cell RNA-seq atlas", abstract="single-cell study")
    summary = Summary(tldr="t")  # no topic/difficulty from the model
    rec = build_record(paper, summary)
    assert rec["subfield_tags"] == ["single-cell"]
    assert rec["difficulty_level"] in {"intro", "intermediate", "advanced"}


def test_is_canonical_tag():
    assert is_canonical_tag("genomics") is True
    assert is_canonical_tag("not-a-real-tag") is False
