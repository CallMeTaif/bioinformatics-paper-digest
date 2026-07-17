# Bioinformatics Paper Digest

An automated pipeline that discovers strong open-access bioinformatics papers,
summarizes them with AI, (later) verifies the summaries with a second AI, and
publishes each to a static website. Scope: **broad bioinformatics**.

See [the build spec](../Bioinformatics_Paper_Digest_Project_Plan.md) for the full design.

## Layout

```
web/            Astro static site (home grid + paper detail) + admin review page (Phase 2)
pipeline/       Python pipeline
  sources/      one module per source (Phase 1: openalex, europepmc)
  rank/         scoring + two-lane blend + dedup (Phase 2)
  llm/          swappable summarize()/verify() interface
  publish/      Supabase writes + PDF license gate
  topics.py     BROAD BIOINFORMATICS scope (the on-topic definition)
  config.py     loads .env, exposes settings
  run.py        entrypoint the scheduler calls (Phase 1)
supabase/       schema.sql
```

## Quick start (pipeline)

```bash
cd pipeline
python3 -m venv ../.venv
source ../.venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env      # then fill in keys
python -m pipeline.config       # prints a secret-safe settings check
```

Runs default to **`DRY_RUN=true`** — no paid API calls, no DB writes; the
pipeline prints what it *would* do. Flip `DRY_RUN=false` in `.env` for a real run.

## Status

- [x] **Phase 0** — scaffold, schema, env, topic scope
- [ ] **Phase 1** — OpenAlex → Europe PMC → summarize → Astro site (MVP)
- [ ] **Phase 2** — verifier + review queue + more sources + scheduler
- [ ] **Phase 3** — search, filters, RSS, analytics
