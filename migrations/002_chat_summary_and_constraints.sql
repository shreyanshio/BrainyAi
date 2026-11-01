-- ==============================================================================
-- BRAINY AI — CHAT SESSIONS & MESSAGES CONSTRAINTS & SUMMARY MIGRATION
-- Migration: 002_chat_summary_and_constraints.sql
-- Description:
--   1. Adds rolling context summary columns to public.chat_sessions if not existing.
--   2. Adds unique index/constraint for idempotency_key on public.chat_messages.
--   3. Creates public.ai_request_logs telemetry table.
-- ==============================================================================

-- 1. ADD SUMMARY AND EXPANDED METADATA COLUMNS TO CHAT_SESSIONS
ALTER TABLE public.chat_sessions 
ADD COLUMN IF NOT EXISTS context_summary TEXT,
ADD COLUMN IF NOT EXISTS summary_through_message_id BIGINT DEFAULT 0,
ADD COLUMN IF NOT EXISTS summary_updated_at TIMESTAMPTZ DEFAULT timezone('utc', now()),
ADD COLUMN IF NOT EXISTS last_message_at TIMESTAMPTZ DEFAULT timezone('utc', now()),
ADD COLUMN IF NOT EXISTS is_saved BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS is_pinned BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT FALSE;

-- 2. CREATE IDEMPOTENCY CONSTRAINT ON CHAT_MESSAGES
-- Avoids HTTP 400 when PostgREST performs upserts with on_conflict=session_id,idempotency_key
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_chat_messages_session_idempotency'
    ) THEN
        ALTER TABLE public.chat_messages
        ADD CONSTRAINT uq_chat_messages_session_idempotency UNIQUE (session_id, idempotency_key);
    END IF;
EXCEPTION
    WHEN duplicate_table THEN
        NULL;
    WHEN undefined_column THEN
        -- If idempotency_key column doesn't exist, create it first then add constraint
        ALTER TABLE public.chat_messages ADD COLUMN IF NOT EXISTS idempotency_key TEXT;
        ALTER TABLE public.chat_messages ADD CONSTRAINT uq_chat_messages_session_idempotency UNIQUE (session_id, idempotency_key);
END $$;

-- Index for speedy idempotency lookup
CREATE INDEX IF NOT EXISTS idx_chat_messages_idempotency ON public.chat_messages (session_id, idempotency_key);

-- 3. AI REQUEST LOGS (TELEMETRY) TABLE
CREATE TABLE IF NOT EXISTS public.ai_request_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id TEXT NOT NULL,
    user_id BIGINT,
    task TEXT NOT NULL,
    depth TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    latency_ms DOUBLE PRECISION,
    ttft_ms DOUBLE PRECISION,
    input_tokens INT,
    output_tokens INT,
    cost_usd NUMERIC(10, 6) DEFAULT 0,
    status TEXT NOT NULL,
    escalation_reason TEXT,
    is_estimated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_ai_request_logs_req ON public.ai_request_logs (request_id);
CREATE INDEX IF NOT EXISTS idx_ai_request_logs_created ON public.ai_request_logs (created_at DESC);

-- Enable RLS & service role policy for ai_request_logs
ALTER TABLE public.ai_request_logs ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE policyname = 'service_role_all_ai_request_logs'
    ) THEN
        CREATE POLICY service_role_all_ai_request_logs ON public.ai_request_logs FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;
