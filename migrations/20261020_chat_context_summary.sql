-- Add encrypted rolling-memory fields to the existing conversation table.
-- This is additive: it creates no duplicate tables and does not change or
-- remove existing conversation/message data. Existing RLS/grants continue to
-- govern these columns; the Python service writes them with its server key.

begin;

alter table public.chat_sessions
  add column if not exists context_summary text,
  add column if not exists summary_through_message_id bigint,
  add column if not exists summary_updated_at timestamptz;

comment on column public.chat_sessions.context_summary is
  'Encrypted compact memory of older turns in this conversation; never public.';
comment on column public.chat_sessions.summary_through_message_id is
  'Highest chat_messages.id fully represented by context_summary.';
comment on column public.chat_sessions.summary_updated_at is
  'UTC timestamp of the last successful rolling summary refresh.';

commit;

-- Verify after applying:
-- select column_name, data_type
-- from information_schema.columns
-- where table_schema = 'public' and table_name = 'chat_sessions'
--   and column_name in ('context_summary', 'summary_through_message_id', 'summary_updated_at');
