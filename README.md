# Bioinformatics Paper Digest

An automated pipeline that discovers strong open-access bioinformatics papers,
summarizes them with AI, **independently verifies each summary with a second AI
from a different model family**, and publishes them to a static website.

Scope: **broad bioinformatics** — genomics, single-cell, proteomics, phylogenetics,
systems biology, methods/algorithms, plus computational clinical informatics.

## How it works

```
discover (4 sources, two-lane blend)     OpenAlex + bioRxiv + medRxiv
   ↓
skip already-published                   never re-summarize or repost a paper
   ↓
abstract pre-screen (cheap model)        drop off-topic/weak papers before paying
   ↓
resolve full text                        JATS XML → Europe PMC → open PDF
   ↓
Crossref license                         authoritative host-vs-link decision
   ↓
SUMMARIZE  (Gemini)                      fixed 7-section template
   ↓
VERIFY     (Claude Opus)                 different model family, checks every claim
   ↓
gate → publish | flag for review         high-confidence pass auto-publishes
```

**Why two model families?** A model checking its own family's output shares its
blind spots. Using a different family for verification catches more.

Honest limits: automated checking catches most errors, not all. Every summary is
labeled AI-generated and links to the original. Preprints are labeled as not
peer-reviewed. PDFs are only ever hosted when the license permits redistribution.

## Layout

```
web/            Astro static site — home, library (search/filters), paper detail, about
pipeline/
  sources/      openalex, rxiv (bioRxiv/medRxiv), europepmc, crossref, pdf,
                discovery (merge+dedup), fulltext (resolver)
  llm/          swappable summarize() / verify() / prescreen() interfaces
                (mock, gemini, claude) — provider chosen by env
  publish/      record building, copyright gate, store (local JSON or Supabase)
  topics.py     the on-topic definition        config.py  env settings
  run.py        entrypoint the scheduler calls  tests/    60 unit tests
supabase/       schema.sql
```

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r pipeline/requirements.txt
cp .env.example .env          # then fill in keys
python -m pipeline.config     # secret-safe settings check
python -m pytest pipeline/tests -q

python -u -m pipeline.run --limit 5    # DRY_RUN=true by default (no paid calls)
```

Runs default to **`DRY_RUN=true`** — mock models, no cost. Set `DRY_RUN=false`
in `.env` (with API keys) for a real run. Repeat runs are safe: already-published
papers are skipped automatically.

```bash
cd web && npm install && npm run dev     # site at localhost:4321
```

## Deploying the site

The site is a static Astro build in `web/`, so any static host works.

**Vercel (recommended):**
1. Sign in to [vercel.com](https://vercel.com) with GitHub → **Add New Project**.
2. Pick this repository.
3. Set **Root Directory** to `web` (the site lives in a subfolder). Astro is
   auto-detected — no other settings needed.
4. **Deploy.** Every future `git push` redeploys automatically.

Afterwards, set `site` in `web/astro.config.mjs` to the real URL (for SEO/sitemap).

## Cost

~$0.18–0.20 per published paper (summarize + verify), so roughly **$5/month** at
3 posts/week. Hosting and the scheduler are free; no always-on server or GPU.

## Status

- [x] **Phase 0** — scaffold, schema, env, topic scope
- [x] **Phase 1** — discovery → full text → summarize → static site
- [x] **Phase 2** — cross-family verifier + publish gate, abstract pre-screen,
      bioRxiv/medRxiv fresh lane, two-lane blend, Crossref licenses, PDF text
      extraction, posted-paper dedup
- [x] **Phase 3 (partial)** — searchable/filterable library
- [ ] Scheduled M/W/F runs, review queue, RSS, PDF hosting
