-- Additive migration: move product quota state from process-local files to
-- a shared, atomic Supabase/PostgreSQL store. Existing active file quota data
-- cannot be safely merged across workers; apply this before deploying the code.

create table if not exists public.user_quotas (
  user_id bigint primary key,
  used integer not null default 0 check (used >= 0),
  window_start timestamptz not null default now(),
  reset_at timestamptz not null default (now() + interval '5 hours'),
  updated_at timestamptz not null default now()
);

alter table if exists public.user_memory
  add column if not exists preferences jsonb not null default '{}'::jsonb;

alter table public.user_quotas enable row level security;
drop policy if exists "Service role full access on user_quotas" on public.user_quotas;
create policy "Service role full access on user_quotas"
  on public.user_quotas for all using (auth.role() = 'service_role');

create or replace function public.brainy_get_user_quota(p_user_id bigint, p_limit integer, p_window_hours integer)
returns jsonb language plpgsql security definer set search_path = public as $$
declare q public.user_quotas%rowtype;
begin
  insert into public.user_quotas(user_id, window_start, reset_at)
    values (p_user_id, now(), now() + make_interval(hours => p_window_hours))
  on conflict (user_id) do nothing;
  update public.user_quotas set used = 0, window_start = now(),
    reset_at = now() + make_interval(hours => p_window_hours), updated_at = now()
    where user_id = p_user_id and reset_at <= now();
  select * into q from public.user_quotas where user_id = p_user_id;
  return jsonb_build_object('used', q.used, 'remaining', greatest(0, p_limit - q.used),
    'reset_at', q.reset_at, 'window_hours', p_window_hours);
end;
$$;

create or replace function public.brainy_consume_user_quota(
  p_user_id bigint, p_limit integer, p_window_hours integer
) returns jsonb language plpgsql security definer set search_path = public as $$
declare q public.user_quotas%rowtype; allowed boolean;
begin
  insert into public.user_quotas(user_id, used, window_start, reset_at)
    values (p_user_id, 0, now(), now() + make_interval(hours => p_window_hours))
    on conflict (user_id) do nothing;
  update public.user_quotas set used = 0, window_start = now(),
    reset_at = now() + make_interval(hours => p_window_hours), updated_at = now()
    where user_id = p_user_id and reset_at <= now();
  select * into q from public.user_quotas where user_id = p_user_id for update;
  allowed := q.used < p_limit;
  if allowed then
    update public.user_quotas set used = used + 1, updated_at = now()
      where user_id = p_user_id returning * into q;
  end if;
  return jsonb_build_object('allowed', allowed, 'used', q.used,
    'remaining', greatest(0, p_limit - q.used), 'reset_at', q.reset_at,
    'window_hours', p_window_hours);
end;
$$;

create or replace function public.brainy_refund_user_quota(p_user_id bigint, p_limit integer, p_window_hours integer)
returns jsonb language plpgsql security definer set search_path = public as $$
declare q public.user_quotas%rowtype;
begin
  update public.user_quotas set used = greatest(0, used - 1), updated_at = now()
    where user_id = p_user_id and reset_at > now() returning * into q;
  if not found then
    return public.brainy_get_user_quota(p_user_id, p_limit, p_window_hours);
  end if;
  return jsonb_build_object('used', q.used, 'remaining', greatest(0, p_limit - q.used),
    'reset_at', q.reset_at, 'window_hours', p_window_hours);
end;
$$;

revoke all on function public.brainy_get_user_quota(bigint, integer, integer) from public, anon, authenticated;
revoke all on function public.brainy_consume_user_quota(bigint, integer, integer) from public, anon, authenticated;
revoke all on function public.brainy_refund_user_quota(bigint, integer, integer) from public, anon, authenticated;
grant execute on function public.brainy_get_user_quota(bigint, integer, integer) to service_role;
grant execute on function public.brainy_consume_user_quota(bigint, integer, integer) to service_role;
grant execute on function public.brainy_refund_user_quota(bigint, integer, integer) to service_role;

-- Shared atomic fixed-window limiter buckets; only a SHA-256 key is stored.
create table if not exists public.rate_limit_buckets (
  bucket_key text primary key,
  window_start timestamptz not null,
  request_count integer not null default 0,
  updated_at timestamptz not null default now()
);
alter table public.rate_limit_buckets enable row level security;
drop policy if exists "Service role full access on rate_limit_buckets" on public.rate_limit_buckets;
create policy "Service role full access on rate_limit_buckets"
  on public.rate_limit_buckets for all using (auth.role() = 'service_role');

create or replace function public.brainy_check_rate_limit(
  p_bucket_key text, p_limit integer, p_window_seconds integer
) returns jsonb language plpgsql security definer set search_path = public as $$
declare b public.rate_limit_buckets%rowtype; reset_seconds integer;
begin
  insert into public.rate_limit_buckets(bucket_key, window_start, request_count)
    values (p_bucket_key, now(), 1)
    on conflict (bucket_key) do update set
      request_count = case
        when rate_limit_buckets.window_start <= now() - make_interval(secs => p_window_seconds) then 1
        else rate_limit_buckets.request_count + 1 end,
      window_start = case
        when rate_limit_buckets.window_start <= now() - make_interval(secs => p_window_seconds) then now()
        else rate_limit_buckets.window_start end,
      updated_at = now()
    returning * into b;
  reset_seconds := greatest(1, ceil(extract(epoch from
    (b.window_start + make_interval(secs => p_window_seconds)) - now()))::integer);
  return jsonb_build_object('allowed', b.request_count <= p_limit,
    'remaining', greatest(0, p_limit - b.request_count), 'retry_after', reset_seconds,
    'reset_at', b.window_start + make_interval(secs => p_window_seconds));
end;
$$;
revoke all on function public.brainy_check_rate_limit(text, integer, integer) from public, anon, authenticated;
grant execute on function public.brainy_check_rate_limit(text, integer, integer) to service_role;
