-- Add persistent workspace state to the existing chat_sessions table.
-- Apply after 20261018_chat_owner_integrity.sql and 20261018_chat_idempotency.sql.
-- Additive only: existing conversations and messages are preserved.

alter table public.chat_sessions
  add column if not exists is_saved boolean not null default false,
  add column if not exists is_pinned boolean not null default false,
  add column if not exists is_archived boolean not null default false;

create index if not exists idx_chat_sessions_owner_saved_activity
  on public.chat_sessions (user_id, last_message_at desc nulls last, created_at desc)
  where is_saved = true;

create index if not exists idx_chat_sessions_owner_pinned_activity
  on public.chat_sessions (user_id, last_message_at desc nulls last, created_at desc)
  where is_pinned = true;

create index if not exists idx_chat_sessions_owner_archived_activity
  on public.chat_sessions (user_id, last_message_at desc nulls last, created_at desc)
  where is_archived = true;

-- Access remains through the existing server API and service-role policy.
-- Do not grant anon/authenticated access to private chat data.
