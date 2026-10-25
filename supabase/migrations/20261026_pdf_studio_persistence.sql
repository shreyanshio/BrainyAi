-- ── BrainyAi PDF Study Studio - Durable Storage & Schema Migration ──────────
-- Version: 20261026_pdf_studio_persistence
-- Provides durable PostgreSQL persistence and Supabase Storage security for PDF documents,
-- extracted pages, structured revision notes, MCQs, quiz attempts, flashcards, and progress tracking.

-- 1. Create Private Storage Bucket for Study PDFs
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'study-pdfs',
  'study-pdfs',
  false,
  26214400, -- 25MB max
  array['application/pdf']
)
on conflict (id) do update set
  public = false,
  file_size_limit = 26214400,
  allowed_mime_types = array['application/pdf'];

-- 2. User Documents Table
create table if not exists public.user_documents (
  id uuid primary key default gen_random_uuid(),
  user_id bigint not null,
  filename text not null,
  file_size bigint not null default 0,
  page_count integer not null default 0,
  storage_path text,
  processing_status text not null default 'ready',
  error_message text,
  ocr_status text not null default 'none',
  content_hash text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_user_documents_user_id on public.user_documents (user_id, created_at desc);
create index if not exists idx_user_documents_status on public.user_documents (processing_status);

-- 3. Document Pages Table (Page-Aware Text Index)
create table if not exists public.document_pages (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.user_documents(id) on delete cascade,
  user_id bigint not null,
  page_number integer not null,
  text_content text not null default '',
  token_count integer not null default 0,
  has_images boolean not null default false,
  headings jsonb not null default '[]'::jsonb,
  extraction_method text not null default 'native_text',
  extraction_status text not null default 'success',
  created_at timestamptz not null default now()
);

create index if not exists idx_document_pages_doc_page on public.document_pages (document_id, page_number);
create index if not exists idx_document_pages_user on public.document_pages (user_id);

-- 4. Document Notes Table
create table if not exists public.document_notes (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.user_documents(id) on delete cascade,
  user_id bigint not null,
  title text not null default 'Revision Notes',
  depth text not null default 'BALANCED',
  content text not null,
  citations jsonb not null default '[]'::jsonb,
  structured_data jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_document_notes_doc_user on public.document_notes (document_id, user_id, created_at desc);

-- 5. Document Quizzes Table
create table if not exists public.document_quizzes (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.user_documents(id) on delete cascade,
  user_id bigint not null,
  title text not null default 'Document Quiz',
  questions jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_document_quizzes_doc_user on public.document_quizzes (document_id, user_id, created_at desc);

-- 6. Document Quiz Attempts Table
create table if not exists public.document_quiz_attempts (
  id uuid primary key default gen_random_uuid(),
  quiz_id uuid not null references public.document_quizzes(id) on delete cascade,
  user_id bigint not null,
  score integer not null default 0,
  total integer not null default 0,
  percentage numeric(5,2) not null default 0.00,
  details jsonb not null default '[]'::jsonb,
  feedback jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_quiz_attempts_quiz_user on public.document_quiz_attempts (quiz_id, user_id, created_at desc);

-- 7. Document Flashcards Table
create table if not exists public.document_flashcards (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.user_documents(id) on delete cascade,
  user_id bigint not null,
  cards jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_document_flashcards_doc_user on public.document_flashcards (document_id, user_id, created_at desc);

-- 8. Document Study Progress Table
create table if not exists public.document_study_progress (
  id uuid primary key default gen_random_uuid(),
  user_id bigint not null,
  document_id uuid not null references public.user_documents(id) on delete cascade,
  notes_generated boolean not null default false,
  quizzes_taken integer not null default 0,
  best_quiz_score integer not null default 0,
  cards_reviewed integer not null default 0,
  last_studied_at timestamptz not null default now(),
  constraint uq_user_document_progress unique (user_id, document_id)
);

create index if not exists idx_study_progress_user_doc on public.document_study_progress (user_id, document_id);

-- ── 9. ROW LEVEL SECURITY (RLS) POLICIES ──────────────────────────────────────

alter table public.user_documents enable row level security;
alter table public.document_pages enable row level security;
alter table public.document_notes enable row level security;
alter table public.document_quizzes enable row level security;
alter table public.document_quiz_attempts enable row level security;
alter table public.document_flashcards enable row level security;
alter table public.document_study_progress enable row level security;

-- Drop existing policies if any to ensure clean idempotent migration
drop policy if exists "Users can only access their own documents" on public.user_documents;
drop policy if exists "Users can only access their own document pages" on public.document_pages;
drop policy if exists "Users can only access their own document notes" on public.document_notes;
drop policy if exists "Users can only access their own document quizzes" on public.document_quizzes;
drop policy if exists "Users can only access their own quiz attempts" on public.document_quiz_attempts;
drop policy if exists "Users can only access their own flashcards" on public.document_flashcards;
drop policy if exists "Users can only access their own study progress" on public.document_study_progress;

-- Service role has full permissions on all PDF tables
grant select, insert, update, delete
  on public.user_documents, public.document_pages, public.document_notes,
     public.document_quizzes, public.document_quiz_attempts,
     public.document_flashcards, public.document_study_progress
  to service_role;

-- Storage bucket access policies
-- Only allow access to user's isolated folder <user_id>/...
drop policy if exists "Users can access own study-pdfs files" on storage.objects;
create policy "Users can access own study-pdfs files"
  on storage.objects
  for all
  using (
    bucket_id = 'study-pdfs' and
    (auth.uid()::text = (storage.foldername(name))[1] or auth.role() = 'service_role')
  )
  with check (
    bucket_id = 'study-pdfs' and
    (auth.uid()::text = (storage.foldername(name))[1] or auth.role() = 'service_role')
  );
