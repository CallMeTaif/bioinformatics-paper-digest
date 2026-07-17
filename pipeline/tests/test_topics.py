"""Subfield tagging + abstract reconstruction (offline)."""
from pipeline.topics import tag_for_text, DEFAULT_TAG
from pipeline.sources.openalex import _reconstruct_abstract


def test_tag_single_cell():
    assert tag_for_text("A single-cell RNA-seq atlas of the brain")[0] == "single-cell"


def test_tag_proteomics():
    assert tag_for_text("Protein structure prediction with transformers")[0] == "proteomics"


def test_tag_ml_in_bio():
    assert tag_for_text("A deep learning foundation model for DNA")[0] == "ml-in-bio"


def test_tag_fallback():
    assert tag_for_text("An unrelated topic entirely") == DEFAULT_TAG


def test_reconstruct_abstract_orders_words():
    inv = {"Hello": [0], "brave": [2], "world": [3], "you": [1]}
    assert _reconstruct_abstract(inv) == "Hello you brave world"


def test_reconstruct_abstract_empty():
    assert _reconstruct_abstract(None) is None
    assert _reconstruct_abstract({}) is None
