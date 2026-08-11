-- Per-user reading lists for BioRead.
-- Paste this into Supabase → SQL Editor → New query → Run.
--
-- One row per (user, paper). `status` is the reading state. Row-level security
-- guarantees each signed-in user can only ever see and change their OWN rows.

create table if not exists public.reading_list (
  user_id    uuid        not null references auth.users (id) on delete cascade,
  paper_slug text        not null,
  status     text        not null check (status in ('want', 'reading', 'done')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, paper_slug)
);

-- Keep updated_at fresh on every change.
create or replace function public.touch_reading_list()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

drop trigger if exists trg_touch_reading_list on public.reading_list;
create trigger trg_touch_reading_list
  before update on public.reading_list
  for each row execute function public.touch_reading_list();

-- Lock the table down: no access unless a policy allows it.
alter table public.reading_list enable row level security;

drop policy if exists "read own rows"   on public.reading_list;
drop policy if exists "insert own rows" on public.reading_list;
drop policy if exists "update own rows" on public.reading_list;
drop policy if exists "delete own rows" on public.reading_list;

create policy "read own rows"   on public.reading_list
  for select using (auth.uid() = user_id);
create policy "insert own rows" on public.reading_list
  for insert with check (auth.uid() = user_id);
create policy "update own rows" on public.reading_list
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "delete own rows" on public.reading_list
  for delete using (auth.uid() = user_id);
