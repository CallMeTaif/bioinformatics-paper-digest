"""Mock pre-screen (keyword filter) + prompt assembly."""
from pipeline.sources.base import Paper
from pipeline.llm.prescreen import MockPrescreener, build_prescreen_prompt


def test_mock_keeps_on_topic():
    p = Paper(title="A single-cell RNA-seq atlas", abstract="transcriptomics of the brain")
    d = MockPrescreener().screen([p])[0]
    assert d.keep is True and d.score > 0


def test_mock_drops_off_topic():
    p = Paper(title="A study of medieval poetry", abstract="literary analysis of sonnets")
    d = MockPrescreener().screen([p])[0]
    assert d.keep is False


def test_mock_returns_one_decision_per_paper():
    papers = [Paper(title="genomics paper"), Paper(title="unrelated cooking blog")]
    decisions = MockPrescreener().screen(papers)
    assert len(decisions) == 2


def test_prompt_includes_indices_and_scope():
    papers = [Paper(title="P0", abstract="a"), Paper(title="P1", abstract="b")]
    prompt = build_prescreen_prompt(papers)
    assert "[0]" in prompt and "[1]" in prompt
    assert "bioinformatics" in prompt.lower()
