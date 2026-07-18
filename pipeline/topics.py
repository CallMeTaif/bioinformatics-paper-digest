"""
Topic scope for discovery: BROAD BIOINFORMATICS.

This is the single source of truth for "what counts as on-topic." Discovery
queries OpenAlex with these terms; tagging uses SUBFIELD_TAGS; the (Phase 2)
LLM pre-screen prompt is seeded from SCOPE_DESCRIPTION.

Keep this list tunable — it directly controls what the site publishes.
"""

# One-line description handed to the abstract pre-screen (Phase 2) and shown
# on the About page. Edit this to sharpen or widen the scope.
SCOPE_DESCRIPTION = (
    "Broad bioinformatics and computational biology: genomics, sequence and "
    "structural analysis, transcriptomics and single-cell, proteomics, "
    "phylogenetics, systems biology, methods/algorithms/software, plus "
    "computational clinical/medical informatics and drug discovery."
)

# Broad keyword net for OpenAlex title/abstract search. Grouped only for
# readability; discovery flattens them. Add/remove freely.
INCLUDE_KEYWORDS = [
    # --- core computational biology ---
    "bioinformatics",
    "computational biology",
    "genomics",
    "sequence analysis",
    "sequence alignment",
    "variant calling",
    "genome assembly",
    "transcriptomics",
    "RNA-seq",
    "single-cell",
    "single cell sequencing",
    "phylogenetics",
    "phylogenomics",
    "proteomics",
    "protein structure prediction",
    "metagenomics",
    "epigenomics",
    "gene expression",
    "regulatory genomics",
    # --- methods / ML in biology ---
    "deep learning genomics",
    "machine learning biology",
    "protein language model",
    "foundation model biology",
    "graph neural network molecular",
    # --- systems / clinical / discovery ---
    "systems biology",
    "network biology",
    "clinical informatics",
    "biomedical informatics",
    "electronic health records",
    "drug discovery computational",
    "drug-target interaction",
    "pharmacogenomics",
]

# Terms that usually signal off-topic wet-lab-only or unrelated work. Used as a
# soft negative signal in ranking / pre-screen, never a hard filter.
SOFT_EXCLUDE_KEYWORDS = [
    "case report",
    "clinical trial protocol",
    "qualitative study",
]

# Maps a matched keyword (substring, case-insensitive) to a display subfield tag
# with a nucleotide accent color slot (see web design system, §8). First match wins;
# order matters. Anything unmatched falls back to "bioinformatics".
SUBFIELD_TAGS = [
    (("single-cell", "single cell", "scrna"), "single-cell", "A"),
    (("transcriptom", "rna-seq", "gene expression"), "transcriptomics", "A"),
    (("proteom", "protein structure", "protein language"), "proteomics", "C"),
    (("genome assembly", "variant calling", "sequence align", "genomics"), "genomics", "C"),
    (("phylogen",), "phylogenetics", "G"),
    (("metagenom", "microbiome"), "metagenomics", "G"),
    (("epigenom", "regulatory genomics", "methylation"), "epigenomics", "G"),
    (("deep learning", "machine learning", "neural network", "foundation model"), "ml-in-bio", "T"),
    (("systems biology", "network biology"), "systems-biology", "T"),
    (("clinical", "health record", "biomedical informatics"), "clinical-informatics", "T"),
    (("drug", "pharmaco"), "drug-discovery", "C"),
]

DEFAULT_TAG = ("bioinformatics", "A")

# The closed vocabulary the summarizer must choose from (keeps tags consistent
# with the site's filters and nucleotide accent colours). Derived from
# SUBFIELD_TAGS so there is a single source of truth.
CANONICAL_TAGS: list[str] = [tag for _, tag, _ in SUBFIELD_TAGS] + [DEFAULT_TAG[0]]
_ACCENT_BY_TAG: dict[str, str] = {tag: accent for _, tag, accent in SUBFIELD_TAGS}
_ACCENT_BY_TAG[DEFAULT_TAG[0]] = DEFAULT_TAG[1]

DIFFICULTY_LEVELS = ("intro", "intermediate", "advanced")


def accent_for_tag(tag: str) -> str:
    """Nucleotide accent (A/C/G/T) for a canonical tag; default if unknown."""
    return _ACCENT_BY_TAG.get(tag, DEFAULT_TAG[1])


def is_canonical_tag(tag: str) -> bool:
    return tag in _ACCENT_BY_TAG

# Optional: exact OpenAlex concept IDs to AND/OR into discovery. Leave empty to
# rely on keyword search. Fill these once verified against the live OpenAlex API
# (e.g. GET https://api.openalex.org/concepts?search=bioinformatics).
OPENALEX_CONCEPT_IDS: list[str] = []


def tag_for_text(text: str) -> tuple[str, str]:
    """Return (subfield_tag, nucleotide_accent) for a title/abstract blob."""
    low = (text or "").lower()
    for needles, tag, accent in SUBFIELD_TAGS:
        if any(n in low for n in needles):
            return tag, accent
    return DEFAULT_TAG
