-- Bioinformatics Paper Digest — core schema
-- Run in the Supabase SQL editor (or via `supabase db push`).

create extension if not exists "pgcrypto";  -- for gen_random_uuid()

create table if not exists papers (
    id                uuid primary key default gen_random_uuid(),
    slug              text unique,                 -- URL slug for the detail page
    doi               text unique,                 -- dedup key (nullable: some preprints lack a DOI at first)
    title             text not null,
    authors           text[],                      -- ordered author display names
    venue             text,                        -- journal or preprint server
    publication_date  date,
    source            text not null                -- which module found it
        check (source in ('openalex','s2','crossref','pubmed','europepmc','biorxiv','medrxiv')),
    is_preprint       boolean not null default false,
    oa_status         text,                        -- gold | green | hybrid | bronze | closed
    license           text,                        -- cc-by | cc-by-nc | cc0 | cc-by-sa | none | unknown
    original_url      text,                        -- DOI / landing page
    pdf_original_url  text,
    hosted_pdf_path   text,                        -- set ONLY when license is on the allowlist
    can_host          boolean not null default false, -- license permits hosting (Phase 2 acts on it)
    abstract          text,
    subfield_tags     text[] default '{}',
    tag_accent        text,                        -- nucleotide color slot (A/C/G/T) for the primary tag
    difficulty_level  text check (difficulty_level in ('intro','intermediate','advanced')),

    -- structured 7-section summary (see §6 template)
    summary           jsonb,                       -- {tldr, problem, methods, findings, why, limitations, takeaway}
    summary_provider  text,                        -- which model wrote it (e.g. 'mock', 'google')
    used_full_text    boolean not null default false, -- true if summarized from full text, not just abstract

    -- verifier (Phase 2; nullable until then)
    verifier_score    numeric,                     -- 0..1 faithfulness/quality
    verifier_verdict  text check (verifier_verdict in ('pass','flag')),

    status            text not null default 'draft'
        check (status in ('draft','queued','flagged','published')),
    date_posted       timestamptz,                 -- set when status -> published

    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now()
);

-- Fast lookups the pipeline and site rely on.
create index if not exists papers_status_posted_idx on papers (status, date_posted desc);
create index if not exists papers_doi_idx            on papers (doi);
create unique index if not exists papers_doi_unique  on papers (doi) where doi is not null;

-- keep updated_at fresh
create or replace function set_updated_at() returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists papers_set_updated_at on papers;
create trigger papers_set_updated_at
    before update on papers
    for each row execute function set_updated_at();

-- Licenses that permit hosting the PDF (see §12). The publish step checks
-- membership here before ever setting hosted_pdf_path.
create table if not exists hostable_licenses (
    license text primary key
);
insert into hostable_licenses (license) values
    ('cc0'), ('cc-by'), ('cc-by-sa')
    -- NOTE: cc-by-nc is intentionally NOT here — only add it if the site is
    -- strictly non-commercial (no ads, no charging). See §12.
on conflict do nothing;
