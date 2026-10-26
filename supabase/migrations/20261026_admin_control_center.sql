-- ── BrainyAi Enterprise Admin Control Center - Database Migration ──────────
-- Version: 20261026_admin_control_center
-- Author: BrainyAi Architecture Team
-- Provides durable PostgreSQL tables, indexes, and RLS policies for:
-- 1. Administrator roles & RBAC
-- 2. Request-level AI telemetry & token accounting
-- 3. Administrator audit logging
-- 4. Provider rate-limit / quota observations
-- 5. Operational alerts and incidents
-- 6. System configuration overrides

-- 1. Administrator Roles Table
create table if not exists public.admin_roles (
  user_id bigint primary key,
  email text not null,
  role text not null default 'admin',
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_admin_roles_email on public.admin_roles (lower(email));

-- Seed designated initial administrator
insert into public.admin_roles (user_id, email, role, is_active)
values (10001, 'shreyansh101008@gmail.com', 'admin', true)
on conflict (user_id) do update set
  email = 'shreyansh101008@gmail.com',
  role = 'admin',
  is_active = true,
  updated_at = now();

-- 2. AI Request Logs & Token Accounting
create table if not exists public.ai_request_logs (
  id uuid primary key default gen_random_uuid(),
  request_id text not null,
  user_id bigint,
  task text not null,
  depth text not null default 'BALANCED',
  provider text not null,
  model text not null,
  latency_ms double precision not null default 0.0,
  ttft_ms double precision,
  input_tokens integer not null default 0,
  output_tokens integer not null default 0,
  total_tokens integer not null default 0,
  status text not null default 'success',
  fallback_used boolean not null default false,
  fallback_from text,
  error_category text,
  cost_usd numeric(10,6) not null default 0.000000,
  is_estimated boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists idx_ai_logs_created_at on public.ai_request_logs (created_at desc);
create index if not exists idx_ai_logs_user_id on public.ai_request_logs (user_id, created_at desc);
create index if not exists idx_ai_logs_provider on public.ai_request_logs (provider, created_at desc);
create index if not exists idx_ai_logs_status on public.ai_request_logs (status);

-- 3. Administrator Audit Logs
create table if not exists public.admin_audit_logs (
  id uuid primary key default gen_random_uuid(),
  actor_id bigint not null,
  actor_email text,
  action text not null,
  target_type text,
  target_id text,
  details jsonb not null default '{}'::jsonb,
  ip_address text,
  created_at timestamptz not null default now()
);

create index if not exists idx_admin_audit_logs_created_at on public.admin_audit_logs (created_at desc);
create index if not exists idx_admin_audit_logs_actor on public.admin_audit_logs (actor_id);

-- 4. Provider Quota & Rate Limit Observations
create table if not exists public.provider_quota_observations (
  id uuid primary key default gen_random_uuid(),
  provider text not null,
  model text,
  limit_requests_per_min integer,
  remaining_requests_per_min integer,
  limit_tokens_per_min integer,
  remaining_tokens_per_min integer,
  limit_requests_per_day integer,
  remaining_requests_per_day integer,
  source text not null default 'response_headers',
  observed_at timestamptz not null default now()
);

create index if not exists idx_quota_observations_provider on public.provider_quota_observations (provider, observed_at desc);

-- 5. Operational Alerts & Incidents
create table if not exists public.admin_system_alerts (
  id uuid primary key default gen_random_uuid(),
  severity text not null default 'warning', -- info, warning, critical
  title text not null,
  message text not null,
  component text not null,
  is_resolved boolean not null default false,
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);

create index if not exists idx_admin_alerts_resolved on public.admin_system_alerts (is_resolved, created_at desc);

-- 6. System Configuration Overrides
create table if not exists public.admin_system_config (
  key text primary key,
  value jsonb not null,
  description text,
  updated_by bigint,
  updated_at timestamptz not null default now()
);

-- Seed initial operational defaults
insert into public.admin_system_config (key, value, description)
values
  ('daily_cost_budget_usd', '10.0'::jsonb, 'Daily maximum spend warning threshold in USD'),
  ('monthly_cost_budget_usd', '150.0'::jsonb, 'Monthly maximum spend warning threshold in USD'),
  ('global_rate_limit_per_min', '120'::jsonb, 'Maximum allowed application queries per minute'),
  ('user_rate_limit_per_hour', '60'::jsonb, 'Maximum allowed queries per user per hour'),
  ('alert_email_notifications', 'true'::jsonb, 'Whether to emit alert logs to designated admin email')
on conflict (key) do nothing;

-- ── 7. ROW LEVEL SECURITY (RLS) POLICIES ──────────────────────────────────────

alter table public.admin_roles enable row level security;
alter table public.ai_request_logs enable row level security;
alter table public.admin_audit_logs enable row level security;
alter table public.provider_quota_observations enable row level security;
alter table public.admin_system_alerts enable row level security;
alter table public.admin_system_config enable row level security;

-- Service role has full access to all admin telemetry tables
grant select, insert, update, delete
  on public.admin_roles, public.ai_request_logs, public.admin_audit_logs,
     public.provider_quota_observations, public.admin_system_alerts,
     public.admin_system_config
  to service_role;
