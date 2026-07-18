"""Publish layer: assemble DB-shaped records and write them to a sink.

Sink selection (see store.save_records):
  - Supabase configured AND not DRY_RUN -> Supabase REST upsert
  - otherwise                           -> local JSON the Astro site reads
"""
from .record import build_record, slugify
from .store import save_records, posted_keys

__all__ = ["build_record", "slugify", "save_records", "posted_keys"]
