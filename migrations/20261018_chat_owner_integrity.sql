-- Add explicit conversation ownership to existing chat messages.
-- This migration reuses chat_sessions, chat_messages, and user_memory; it does
-- not create replacement tables or delete existing rows.

begin;

alter table public.chat_sessions
  add column if not exists updated_at timestamptz,
  add column if not exists last_message_at timestamptz;

update public.chat_sessions
set updated_at = coalesce(updated_at, created_at, now())
where updated_at is null;

alter table public.chat_sessions
  alter column updated_at set default now(),
  alter column updated_at set not null;

alter table public.chat_messages
  add column if not exists user_id bigint;

-- Preserve existing conversations by copying each message owner's ID from its
-- already-linked parent session. No message content is changed.
update public.chat_messages as message
set user_id = conversation.user_id
from public.chat_sessions as conversation
where message.session_id = conversation.id
  and message.user_id is null;

do $$
begin
  if exists (
    select 1 from public.chat_messages where user_id is null
  ) then
    raise exception 'Some chat_messages rows have no matching owner; review those rows before applying this migration';
  end if;
end;
$$;

alter table public.chat_messages
  alter column user_id set not null;

-- PostgreSQL needs this composite key for the ownership-enforcing foreign key.
create unique index if not exists idx_chat_sessions_id_user_id_unique
  on public.chat_sessions(id, user_id);

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'chat_messages_session_owner_fkey'
      and conrelid = 'public.chat_messages'::regclass
  ) then
    alter table public.chat_messages
      add constraint chat_messages_session_owner_fkey
      foreign key (session_id, user_id)
      references public.chat_sessions(id, user_id)
      on delete cascade;
  end if;
end;
$$;

-- Keep session activity current so per-user history can be sorted efficiently.
update public.chat_sessions as conversation
set last_message_at = activity.last_message_at,
    updated_at = greatest(conversation.updated_at, activity.last_message_at)
from (
  select session_id, max(created_at) as last_message_at
  from public.chat_messages
  group by session_id
) as activity
where conversation.id = activity.session_id;

create index if not exists idx_chat_sessions_owner_activity
  on public.chat_sessions(user_id, last_message_at desc, created_at desc);
create index if not exists idx_chat_messages_owner_session_order
  on public.chat_messages(user_id, session_id, id asc);

create or replace function public.brainy_touch_chat_session_activity()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.chat_sessions
  set last_message_at = greatest(coalesce(last_message_at, new.created_at), new.created_at),
      updated_at = greatest(updated_at, new.created_at)
  where id = new.session_id and user_id = new.user_id;
  return new;
end;
$$;

do $$
begin
  if not exists (
    select 1 from pg_trigger
    where tgname = 'chat_messages_touch_session_activity'
      and tgrelid = 'public.chat_messages'::regclass
      and not tgisinternal
  ) then
    create trigger chat_messages_touch_session_activity
      after insert on public.chat_messages
      for each row execute function public.brainy_touch_chat_session_activity();
  end if;
end;
$$;

-- The application authenticates users with its own signed token, not a
-- Supabase Auth JWT. Therefore direct anon/authenticated table access stays
-- denied; the trusted Flask/Bot servers use the private service-role key and
-- must include owner filters in every user-facing query.
alter table public.chat_sessions enable row level security;
alter table public.chat_messages enable row level security;
alter table public.user_memory enable row level security;

do $$
begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'chat_sessions' and policyname = 'Service role full access on chat_sessions') then
    create policy "Service role full access on chat_sessions"
      on public.chat_sessions for all to service_role
      using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'chat_messages' and policyname = 'Service role full access on chat_messages') then
    create policy "Service role full access on chat_messages"
      on public.chat_messages for all to service_role
      using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'user_memory' and policyname = 'Service role full access on user_memory') then
    create policy "Service role full access on user_memory"
      on public.user_memory for all to service_role
      using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
  end if;
end;
$$;

revoke all on public.chat_sessions, public.chat_messages, public.user_memory
  from public, anon, authenticated;
grant select, insert, update, delete
  on public.chat_sessions, public.chat_messages, public.user_memory
  to service_role;
do $$
declare
  message_id_sequence text;
begin
  message_id_sequence := pg_get_serial_sequence('public.chat_messages', 'id');
  if message_id_sequence is not null then
    execute format('grant usage, select on sequence %s to service_role', message_id_sequence);
  end if;
end;
$$;

commit;
