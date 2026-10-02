-- HelAI Telegram notifications: additive migration.
-- Run once in the Supabase SQL editor before turning Telegram on.

begin;

-- Let notifications carry Telegram (unique (match_id, channel) already exists)
alter table public.notifications drop constraint notifications_channel_check;
alter table public.notifications add constraint notifications_channel_check
  check (channel in ('email', 'telegram'));

-- Preference, editable by the user like email_notifications
alter table public.profiles
  add column if not exists notify_telegram boolean not null default false;

-- Chat id: written only by the collector (service key bypasses RLS)
create table if not exists public.telegram_connections (
  user_id      uuid primary key references public.profiles(id) on delete cascade,
  chat_id      bigint not null,
  connected_at timestamptz not null default now()
);
alter table public.telegram_connections enable row level security;
create policy "Users can read own telegram connection"
  on public.telegram_connections for select to authenticated
  using (auth.uid() = user_id);
create policy "Users can delete own telegram connection"
  on public.telegram_connections for delete to authenticated
  using (auth.uid() = user_id);

-- Single-use link codes, at most 30 minutes
create table if not exists public.telegram_link_codes (
  code       text primary key check (code ~ '^[A-Z2-9]{12}$'),
  user_id    uuid not null references public.profiles(id) on delete cascade,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default now() + interval '30 minutes',
  used_at    timestamptz
);
create index if not exists telegram_link_codes_user_idx
  on public.telegram_link_codes (user_id);
alter table public.telegram_link_codes enable row level security;
create policy "Users can create own link codes"
  on public.telegram_link_codes for insert to authenticated
  with check (auth.uid() = user_id
              and used_at is null
              and expires_at <= now() + interval '30 minutes');
create policy "Users can read own link codes"
  on public.telegram_link_codes for select to authenticated
  using (auth.uid() = user_id);

commit;
