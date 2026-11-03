-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- BrainyAi — Admin Analytics, Observability & Audit Logging Schema
-- Version: 004_admin_analytics_and_logs.sql
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- 1. Create ai_request_logs table for durable multi-provider AI telemetry
CREATE TABLE IF NOT EXISTS ai_request_logs (
    id BIGSERIAL PRIMARY KEY,
    request_id TEXT NOT NULL,
    user_id BIGINT,
    task TEXT,
    depth TEXT,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    ttft_ms DOUBLE PRECISION,
    input_tokens INT DEFAULT 0,
    output_tokens INT DEFAULT 0,
    total_tokens INT DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'success' CHECK (status IN ('success', 'error', 'fallback_recovered')),
    fallback_used BOOLEAN DEFAULT false,
    fallback_from TEXT,
    error_category TEXT,
    cost_usd NUMERIC(10, 6) DEFAULT 0.0,
    is_estimated BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Performance Indexes for Dashboard Aggregation and Timeseries Queries
CREATE INDEX IF NOT EXISTS idx_ai_request_logs_created_at ON ai_request_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_request_logs_user_id ON ai_request_logs(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ai_request_logs_provider_model ON ai_request_logs(provider, model);
CREATE INDEX IF NOT EXISTS idx_ai_request_logs_status ON ai_request_logs(status);
CREATE INDEX IF NOT EXISTS idx_ai_request_logs_request_id ON ai_request_logs(request_id);

-- Strict Row Level Security (RLS)
ALTER TABLE ai_request_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Deny direct client access to ai_request_logs" ON ai_request_logs;
CREATE POLICY "Deny direct client access to ai_request_logs"
    ON ai_request_logs
    FOR ALL
    TO anon, authenticated
    USING (false);

DROP POLICY IF EXISTS "service_role_all_ai_request_logs" ON ai_request_logs;
CREATE POLICY "service_role_all_ai_request_logs"
    ON ai_request_logs
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);


-- 2. Create admin_audit_logs table for security and compliance tracking
CREATE TABLE IF NOT EXISTS admin_audit_logs (
    id TEXT PRIMARY KEY,
    actor_id BIGINT,
    actor_email TEXT NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    details JSONB DEFAULT '{}'::jsonb,
    ip_address TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_created_at ON admin_audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_actor_email ON admin_audit_logs(actor_email);
CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_action ON admin_audit_logs(action);

ALTER TABLE admin_audit_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Deny direct client access to admin_audit_logs" ON admin_audit_logs;
CREATE POLICY "Deny direct client access to admin_audit_logs"
    ON admin_audit_logs
    FOR ALL
    TO anon, authenticated
    USING (false);

DROP POLICY IF EXISTS "service_role_all_admin_audit_logs" ON admin_audit_logs;
CREATE POLICY "service_role_all_admin_audit_logs"
    ON admin_audit_logs
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);


-- 3. Create admin_system_alerts table
CREATE TABLE IF NOT EXISTS admin_system_alerts (
    id TEXT PRIMARY KEY,
    severity TEXT NOT NULL DEFAULT 'info' CHECK (severity IN ('info', 'warning', 'error', 'critical')),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    component TEXT NOT NULL,
    is_resolved BOOLEAN DEFAULT false,
    resolved_at TIMESTAMPTZ,
    resolved_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_admin_alerts_resolved ON admin_system_alerts(is_resolved, created_at DESC);

ALTER TABLE admin_system_alerts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Deny direct client access to admin_system_alerts" ON admin_system_alerts;
CREATE POLICY "Deny direct client access to admin_system_alerts"
    ON admin_system_alerts
    FOR ALL
    TO anon, authenticated
    USING (false);

DROP POLICY IF EXISTS "service_role_all_admin_system_alerts" ON admin_system_alerts;
CREATE POLICY "service_role_all_admin_system_alerts"
    ON admin_system_alerts
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);


-- 4. Create admin_system_config table
CREATE TABLE IF NOT EXISTS admin_system_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_by TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE admin_system_config ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Deny direct client access to admin_system_config" ON admin_system_config;
CREATE POLICY "Deny direct client access to admin_system_config"
    ON admin_system_config
    FOR ALL
    TO anon, authenticated
    USING (false);

DROP POLICY IF EXISTS "service_role_all_admin_system_config" ON admin_system_config;
CREATE POLICY "service_role_all_admin_system_config"
    ON admin_system_config
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);


-- 5. Ensure user_quotas table exists with RLS
CREATE TABLE IF NOT EXISTS user_quotas (
    user_id BIGINT PRIMARY KEY,
    used INT DEFAULT 0,
    window_start TIMESTAMPTZ DEFAULT NOW(),
    reset_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_quotas_reset_at ON user_quotas(reset_at);

ALTER TABLE user_quotas ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Deny direct client access to user_quotas" ON user_quotas;
CREATE POLICY "Deny direct client access to user_quotas"
    ON user_quotas
    FOR ALL
    TO anon, authenticated
    USING (false);

DROP POLICY IF EXISTS "service_role_all_user_quotas" ON user_quotas;
CREATE POLICY "service_role_all_user_quotas"
    ON user_quotas
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);


-- 6. Ensure admin_roles table exists with RLS
CREATE TABLE IF NOT EXISTS admin_roles (
    email TEXT PRIMARY KEY,
    role TEXT NOT NULL DEFAULT 'admin',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE admin_roles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Deny direct client access to admin_roles" ON admin_roles;
CREATE POLICY "Deny direct client access to admin_roles"
    ON admin_roles
    FOR ALL
    TO anon, authenticated
    USING (false);

DROP POLICY IF EXISTS "service_role_all_admin_roles" ON admin_roles;
CREATE POLICY "service_role_all_admin_roles"
    ON admin_roles
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
