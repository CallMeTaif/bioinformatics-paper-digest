-- Private pipeline run-stats for the /control dashboard.
-- Paste into Supabase → SQL Editor → New query → Run.
--
-- The pipeline inserts one row per run using the service_role key (which bypasses
-- row-level security). Row-level security then allows ONLY the admin account to
-- read the rows — so the numbers never ship in the site's HTML and no one else,
-- not even via view-source or curl, can retrieve them.

create table if not exists public.run_stats (
  id         bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  data       jsonb       not null
);

create index if not exists run_stats_created_idx on public.run_stats (created_at desc);

alter table public.run_stats enable row level security;

-- Only this account may read. No insert/update/delete policy exists, so writes
-- are possible only with the service_role key (used by the pipeline), never from
-- the browser.
drop policy if exists "admin reads run_stats" on public.run_stats;
create policy "admin reads run_stats" on public.run_stats
  for select using ((auth.jwt() ->> 'email') = 'ai.taif.alharbi@gmail.com');
