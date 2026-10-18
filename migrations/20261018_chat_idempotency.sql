-- Make retried chat writes idempotent within their owning conversation.
-- Existing duplicate keys are reported explicitly and must be reviewed before
-- applying this migration; no user data is deleted automatically.
do $$
begin
  if exists (
    select 1 from public.chat_messages
    where idempotency_key is not null
    group by session_id, idempotency_key
    having count(*) > 1
  ) then
    raise exception 'Duplicate chat idempotency keys exist; review them before applying this migration';
  end if;
end $$;

create unique index if not exists idx_chat_messages_session_idempotency_unique
  on public.chat_messages(session_id, idempotency_key)
  where idempotency_key is not null;
