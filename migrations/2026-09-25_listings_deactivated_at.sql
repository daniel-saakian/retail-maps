-- Run once in the Supabase SQL editor.
-- Lets the digest page show listings that disappeared (leased or pulled) and when.
alter table public.listings
  add column if not exists deactivated_at timestamptz;

-- Speeds up the digest page's "new since" and "removed since" queries.
create index if not exists listings_first_seen_at_idx on public.listings (first_seen_at desc);
create index if not exists listings_deactivated_at_idx on public.listings (deactivated_at desc)
  where active = false;
