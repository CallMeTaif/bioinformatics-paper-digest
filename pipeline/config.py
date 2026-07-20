"""Central config: loads .env once and exposes typed settings.

Nothing here requires secrets to import — missing keys surface only when a
component that needs them actually runs. This keeps `import config` cheap and
lets Phase 1 scaffolding load without any API keys present.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load repo-root .env if present (search upward from this file).
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip())
    except (ValueError, AttributeError):
        return default


# --- sources ---
OPENALEX_MAILTO = os.getenv("OPENALEX_MAILTO", "")
CROSSREF_MAILTO = os.getenv("CROSSREF_MAILTO", "")
SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")

# --- summarizer ---
SUMMARIZER_PROVIDER = os.getenv("SUMMARIZER_PROVIDER", "google")
SUMMARIZER_MODEL = os.getenv("SUMMARIZER_MODEL", "gemini-3.1-pro-preview")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# --- abstract pre-screen (cheap model; reuses GEMINI_API_KEY for google) ---
PRESCREEN_PROVIDER = os.getenv("PRESCREEN_PROVIDER", "google")
PRESCREEN_MODEL = os.getenv("PRESCREEN_MODEL", "gemini-flash-lite-latest")

# --- verifier (Phase 2) ---
VERIFIER_PROVIDER = os.getenv("VERIFIER_PROVIDER", "anthropic")
VERIFIER_MODEL = os.getenv("VERIFIER_MODEL", "claude-opus-4-8")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# --- storage ---
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_PDF_BUCKET = os.getenv("SUPABASE_PDF_BUCKET", "pdfs")
# Storage and database are independent: having storage credentials (for PDF
# hosting) must NOT make the pipeline write records to a Supabase table that
# may not exist. Opt in explicitly.
USE_SUPABASE_DB = _bool("USE_SUPABASE_DB", False)

# --- tuning ---
MAX_CANDIDATES = _int("MAX_CANDIDATES", 15)
PUBLISH_PER_RUN = _int("PUBLISH_PER_RUN", 3)
DRY_RUN = _bool("DRY_RUN", True)
PRESCREEN_ENABLED = _bool("PRESCREEN_ENABLED", True)


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "").strip())
    except (ValueError, AttributeError):
        return default


VERIFY_THRESHOLD = _float("VERIFY_THRESHOLD", 0.8)


def summary_of_settings() -> str:
    """Human-readable, secret-safe dump for `python -m pipeline.config`."""
    def has(v: str) -> str:
        return "set" if v else "MISSING"

    return "\n".join(
        [
            f"DRY_RUN            = {DRY_RUN}",
            f"PUBLISH_PER_RUN    = {PUBLISH_PER_RUN}",
            f"MAX_CANDIDATES     = {MAX_CANDIDATES}",
            f"SUMMARIZER         = {SUMMARIZER_PROVIDER}:{SUMMARIZER_MODEL} (key {has(GEMINI_API_KEY)})",
            f"VERIFIER           = {VERIFIER_PROVIDER}:{VERIFIER_MODEL} (key {has(ANTHROPIC_API_KEY)})",
            f"SUPABASE_URL       = {has(SUPABASE_URL)}",
            f"SUPABASE_SERVICE   = {has(SUPABASE_SERVICE_KEY)}",
            f"OPENALEX_MAILTO    = {OPENALEX_MAILTO or 'MISSING'}",
        ]
    )


if __name__ == "__main__":
    print(summary_of_settings())
