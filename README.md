# BioRead

**Live at [bioread.bio](https://www.bioread.bio)**

An automated pipeline that discovers strong open-access bioinformatics papers,
summarizes them with AI, **independently verifies each summary with a second AI
from a different model family**, and publishes them to a static website — three
new papers a week, hands-off.

Scope: **broad bioinformatics** — genomics, single-cell, proteomics, phylogenetics,
systems biology, methods and algorithms, plus computational clinical informatics.

## How it works

```
discover (multi-source, two-lane blend)   OpenAlex + bioRxiv + medRxiv
   ↓
skip already-published                    never re-summarize or repost a paper
   ↓
abstract pre-screen (cheap model)         drop off-topic / weak papers early
   ↓
resolve full text                         JATS XML → Europe PMC → open PDF
   ↓
license check (Crossref)                  decides host-vs-link for the PDF
   ↓
SUMMARIZE  (Gemini)                        fixed 7-section template
   ↓
VERIFY     (Claude Opus)                   different model family, checks every claim
   ↓
gate → publish | hold for review          high-confidence passes auto-publish
```

**Why two model families?** A model checking its own family's output tends to
share its blind spots. Using a different family for verification catches more.

## Transparency

Summaries are AI-written and link to the original. Automated checking catches
most errors, not all — readers are asked to verify anything important against the
source. Preprints are noted as not peer-reviewed, and a paper's PDF is only ever
hosted when its license permits redistribution; otherwise the site links out.

## Tech stack

- **Site:** Astro static site (fast, SEO-friendly), deployed on Vercel
- **Pipeline:** Python, run on a schedule via GitHub Actions
- **Models:** Google Gemini (summarize) + Anthropic Claude (verify), behind a
  swappable interface
- **Storage:** Supabase Storage for license-cleared PDFs

## Repository layout

```
web/                         Astro site — home, library (search/filters), paper detail, about
pipeline/
  sources/                   openalex, rxiv (bioRxiv/medRxiv), europepmc, crossref, pdf,
                             discovery (merge + dedup), fulltext (resolver)
  llm/                       swappable summarize() / verify() / prescreen() interfaces
  publish/                   record building, license gate, store, PDF hosting
  topics.py                  the on-topic definition
  config.py                  settings loaded from the environment
  run.py                     pipeline entrypoint
  tests/                     unit tests
supabase/                    storage/schema notes
.github/workflows/           scheduled Mon/Wed/Fri publishing
```

## Running locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r pipeline/requirements.txt
cp .env.example .env          # then add your API keys
python -m pytest pipeline/tests -q
python -u -m pipeline.run --limit 1    # DRY_RUN=true by default — mock models, no external calls

cd web && npm install && npm run dev    # site at localhost:4321
```

Set `DRY_RUN=false` in `.env` (with real keys) for a live run. Repeat runs are
safe — already-published papers are skipped automatically.

## License

Code is available for reference. Paper summaries link to their original sources,
which retain their own licenses.
