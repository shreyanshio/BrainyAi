-- ==============================================================================
-- BRAINY AI — PDF STUDY STUDIO DATABASE SCHEMA MIGRATION
-- Migration: 001_pdf_study_studio.sql
-- Description: Creates persistent storage metadata, page indexing, revision notes,
--              exam questions, 4-option quizzes, study flashcards, and progress tracking.
-- ==============================================================================

-- 1. USER DOCUMENTS TABLE
CREATE TABLE IF NOT EXISTS public.user_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL,
    filename TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    page_count INT NOT NULL DEFAULT 1,
    storage_bucket TEXT NOT NULL DEFAULT 'study-pdfs',
    storage_path TEXT NOT NULL,
    mime_type TEXT NOT NULL DEFAULT 'application/pdf',
    processing_status TEXT NOT NULL DEFAULT 'ready', -- 'ready', 'processing', 'error'
    status TEXT NOT NULL DEFAULT 'ready',             -- 'ready', 'expired', 'deleted'
    error_message TEXT,
    ocr_status TEXT DEFAULT 'native_text',
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    last_accessed_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (timezone('utc', now()) + INTERVAL '5 days'),
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_user_documents_user ON public.user_documents (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_documents_status ON public.user_documents (status, expires_at);

-- 2. DOCUMENT PAGES TABLE (Page-level indexed text)
CREATE TABLE IF NOT EXISTS public.document_pages (
    id BIGSERIAL PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES public.user_documents(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    page_number INT NOT NULL,
    text_content TEXT NOT NULL DEFAULT '',
    token_count INT DEFAULT 0,
    has_images BOOLEAN DEFAULT FALSE,
    headings JSONB DEFAULT '[]'::jsonb,
    extraction_method TEXT DEFAULT 'native_text',
    extraction_status TEXT DEFAULT 'success',
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_document_pages_doc ON public.document_pages (document_id, page_number ASC);

-- 3. DOCUMENT NOTES TABLE (Quick, Standard & Detailed Revision Notes)
CREATE TABLE IF NOT EXISTS public.document_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES public.user_documents(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    title TEXT NOT NULL,
    depth TEXT NOT NULL DEFAULT 'STANDARD', -- 'QUICK', 'STANDARD', 'DETAILED'
    content TEXT NOT NULL,
    citations JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_document_notes_doc ON public.document_notes (document_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_document_notes_user ON public.document_notes (user_id);

-- 4. DOCUMENT IMPORTANT QUESTIONS TABLE
CREATE TABLE IF NOT EXISTS public.document_important_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES public.user_documents(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    title TEXT NOT NULL,
    count INT NOT NULL DEFAULT 10,
    category TEXT DEFAULT 'ALL',
    questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_doc_questions_doc ON public.document_important_questions (document_id, created_at DESC);

-- 5. DOCUMENT QUIZZES TABLE (Strictly 4 Options per question)
CREATE TABLE IF NOT EXISTS public.document_quizzes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES public.user_documents(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    title TEXT NOT NULL,
    difficulty TEXT NOT NULL DEFAULT 'MEDIUM',
    questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_document_quizzes_doc ON public.document_quizzes (document_id, created_at DESC);

-- 6. DOCUMENT QUIZ ATTEMPTS TABLE
CREATE TABLE IF NOT EXISTS public.document_quiz_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_id UUID NOT NULL REFERENCES public.document_quizzes(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    score INT NOT NULL DEFAULT 0,
    total INT NOT NULL DEFAULT 0,
    percentage NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    details JSONB NOT NULL DEFAULT '[]'::jsonb,
    feedback JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_doc_quiz_attempts_quiz ON public.document_quiz_attempts (quiz_id);
CREATE INDEX IF NOT EXISTS idx_doc_quiz_attempts_user ON public.document_quiz_attempts (user_id);

-- 7. DOCUMENT FLASHCARDS TABLE
CREATE TABLE IF NOT EXISTS public.document_flashcards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES public.user_documents(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    cards JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_document_flashcards_doc ON public.document_flashcards (document_id, created_at DESC);

-- 8. DOCUMENT STUDY PROGRESS TABLE
CREATE TABLE IF NOT EXISTS public.document_study_progress (
    user_id BIGINT NOT NULL,
    document_id UUID NOT NULL REFERENCES public.user_documents(id) ON DELETE CASCADE,
    notes_generated BOOLEAN NOT NULL DEFAULT FALSE,
    quizzes_taken INT NOT NULL DEFAULT 0,
    best_quiz_score INT NOT NULL DEFAULT 0,
    cards_reviewed INT NOT NULL DEFAULT 0,
    last_studied_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    PRIMARY KEY (user_id, document_id)
);

-- ==============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ==============================================================================
ALTER TABLE public.user_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_pages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_important_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_quizzes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_quiz_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_flashcards ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_study_progress ENABLE ROW LEVEL SECURITY;

-- Allow service role full access for backend worker APIs
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE policyname = 'service_role_all_user_documents'
    ) THEN
        CREATE POLICY service_role_all_user_documents ON public.user_documents FOR ALL TO service_role USING (true) WITH CHECK (true);
        CREATE POLICY service_role_all_document_pages ON public.document_pages FOR ALL TO service_role USING (true) WITH CHECK (true);
        CREATE POLICY service_role_all_document_notes ON public.document_notes FOR ALL TO service_role USING (true) WITH CHECK (true);
        CREATE POLICY service_role_all_document_important_questions ON public.document_important_questions FOR ALL TO service_role USING (true) WITH CHECK (true);
        CREATE POLICY service_role_all_document_quizzes ON public.document_quizzes FOR ALL TO service_role USING (true) WITH CHECK (true);
        CREATE POLICY service_role_all_document_quiz_attempts ON public.document_quiz_attempts FOR ALL TO service_role USING (true) WITH CHECK (true);
        CREATE POLICY service_role_all_document_flashcards ON public.document_flashcards FOR ALL TO service_role USING (true) WITH CHECK (true);
        CREATE POLICY service_role_all_document_study_progress ON public.document_study_progress FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;
