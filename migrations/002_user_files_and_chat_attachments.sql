-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- BrainyAi — Centralized File Storage (Images & PDFs) & Chat Attachments Migration
-- Version: 002_user_files_and_chat_attachments.sql
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- 1. Create user_files table for centralized Google Drive file metadata
CREATE TABLE IF NOT EXISTS user_files (
    id TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    original_filename TEXT NOT NULL,
    storage_filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    file_type TEXT NOT NULL CHECK (file_type IN ('image', 'pdf', 'document')),
    drive_file_id TEXT,
    drive_folder_id TEXT,
    checksum TEXT,
    image_width INT,
    image_height INT,
    upload_status TEXT DEFAULT 'ready' CHECK (upload_status IN ('pending', 'uploading', 'ready', 'failed', 'deleted')),
    source_chat_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

-- Indexes for efficient ownership and drive file lookup
CREATE INDEX IF NOT EXISTS idx_user_files_user_id ON user_files(user_id);
CREATE INDEX IF NOT EXISTS idx_user_files_drive_file ON user_files(drive_file_id) WHERE drive_file_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_user_files_source_chat ON user_files(source_chat_id) WHERE source_chat_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_user_files_status ON user_files(upload_status);
CREATE INDEX IF NOT EXISTS idx_user_files_deleted_at ON user_files(deleted_at) WHERE deleted_at IS NULL;

-- Strict Row Level Security (RLS)
ALTER TABLE user_files ENABLE ROW LEVEL SECURITY;

-- Deny all direct client access (anon, authenticated)
DROP POLICY IF EXISTS "Deny direct client access to user_files" ON user_files;
CREATE POLICY "Deny direct client access to user_files"
    ON user_files
    FOR ALL
    TO anon, authenticated
    USING (false);

-- Backend service role has full access
DROP POLICY IF EXISTS "service_role_all_user_files" ON user_files;
CREATE POLICY "service_role_all_user_files"
    ON user_files
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);


-- 2. Enhance chat_messages with Attachment Reference
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chat_messages' AND column_name = 'attachment_id') THEN
        ALTER TABLE chat_messages ADD COLUMN attachment_id TEXT;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_chat_messages_attachment ON chat_messages(attachment_id) WHERE attachment_id IS NOT NULL;


-- 3. Enhance google_drive_user_folders to store Image Folder references
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'google_drive_user_folders' AND column_name = 'image_folder_id') THEN
        ALTER TABLE google_drive_user_folders ADD COLUMN image_folder_id TEXT;
    END IF;
END $$;
