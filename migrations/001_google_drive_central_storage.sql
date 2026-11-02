-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- BrainyAi — Centralized Private Google Drive Storage Migration
-- Version: 001_google_drive_central_storage.sql
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

-- 1. Owner Google Drive Integration Configuration
-- Stores AES-256-GCM encrypted tokens for the single project owner connection.
-- Strictly backend-only; client access is completely denied via RLS.
CREATE TABLE IF NOT EXISTS google_drive_owner_config (
    id INT PRIMARY KEY DEFAULT 1,
    owner_user_id BIGINT,
    owner_email TEXT,
    encrypted_refresh_token TEXT,
    encrypted_access_token TEXT,
    access_token_expires_at TIMESTAMPTZ,
    root_folder_id TEXT,
    users_folder_id TEXT,
    is_active BOOLEAN DEFAULT FALSE,
    compliance_cleared BOOLEAN DEFAULT FALSE,
    last_health_check_at TIMESTAMPTZ,
    last_health_status TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT single_row_config CHECK (id = 1)
);

ALTER TABLE google_drive_owner_config ENABLE ROW LEVEL SECURITY;

-- Deny all public/anon/authenticated client access to credentials
DROP POLICY IF EXISTS "Deny direct client access to drive config" ON google_drive_owner_config;
CREATE POLICY "Deny direct client access to drive config"
    ON google_drive_owner_config
    FOR ALL
    TO anon, authenticated
    USING (false);


-- 2. User Google Drive Folder Mapping Table
-- Maps each Brainy user ID to their private opaque folder in the owner's Google Drive.
CREATE TABLE IF NOT EXISTS google_drive_user_folders (
    user_id BIGINT PRIMARY KEY,
    opaque_id TEXT NOT NULL UNIQUE,
    user_folder_id TEXT NOT NULL,
    pdf_folder_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_drive_user_folders_opaque ON google_drive_user_folders(opaque_id);

ALTER TABLE google_drive_user_folders ENABLE ROW LEVEL SECURITY;

-- Deny direct client access; backend service role manages mappings
DROP POLICY IF EXISTS "Deny direct client access to drive user folders" ON google_drive_user_folders;
CREATE POLICY "Deny direct client access to drive user folders"
    ON google_drive_user_folders
    FOR ALL
    TO anon, authenticated
    USING (false);


-- 3. Enhance user_documents with Centralized Google Drive Metadata
-- Non-destructive additions to existing user_documents table.
DO $$
BEGIN
    -- Owner User ID (explicit ownership binding)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_documents' AND column_name = 'owner_user_id') THEN
        ALTER TABLE user_documents ADD COLUMN owner_user_id BIGINT;
    END IF;

    -- Google Drive File ID
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_documents' AND column_name = 'drive_file_id') THEN
        ALTER TABLE user_documents ADD COLUMN drive_file_id TEXT;
    END IF;

    -- Google Drive Folder ID
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_documents' AND column_name = 'drive_folder_id') THEN
        ALTER TABLE user_documents ADD COLUMN drive_folder_id TEXT;
    END IF;

    -- SHA-256 Checksum
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_documents' AND column_name = 'checksum') THEN
        ALTER TABLE user_documents ADD COLUMN checksum TEXT;
    END IF;

    -- Upload Status State Machine (local_only, pending, uploading, uploaded, drive_synced, failed, deleted)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_documents' AND column_name = 'upload_status') THEN
        ALTER TABLE user_documents ADD COLUMN upload_status TEXT DEFAULT 'ready';
    END IF;

    -- Soft Deletion Timestamp
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_documents' AND column_name = 'deleted_at') THEN
        ALTER TABLE user_documents ADD COLUMN deleted_at TIMESTAMPTZ;
    END IF;
END $$;

-- Indexes for efficient ownership and drive file lookup
CREATE INDEX IF NOT EXISTS idx_user_documents_owner_lookup ON user_documents(owner_user_id, id);
CREATE INDEX IF NOT EXISTS idx_user_documents_drive_file ON user_documents(drive_file_id) WHERE drive_file_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_user_documents_upload_status ON user_documents(upload_status);

-- Ensure RLS on user_documents strictly isolates users
ALTER TABLE user_documents ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can only select their own documents" ON user_documents;
CREATE POLICY "Users can only select their own documents"
    ON user_documents
    FOR SELECT
    TO authenticated
    USING (user_id = (auth.uid())::text::bigint OR owner_user_id = (auth.uid())::text::bigint);

DROP POLICY IF EXISTS "Users can only delete their own documents" ON user_documents;
CREATE POLICY "Users can only delete their own documents"
    ON user_documents
    FOR DELETE
    TO authenticated
    USING (user_id = (auth.uid())::text::bigint OR owner_user_id = (auth.uid())::text::bigint);


-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- ROLLBACK SCRIPT (Reference only - execute only if rollback is required)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- DROP TABLE IF EXISTS google_drive_owner_config;
-- DROP TABLE IF EXISTS google_drive_user_folders;
-- ALTER TABLE user_documents DROP COLUMN IF EXISTS owner_user_id;
-- ALTER TABLE user_documents DROP COLUMN IF EXISTS drive_file_id;
-- ALTER TABLE user_documents DROP COLUMN IF EXISTS drive_folder_id;
-- ALTER TABLE user_documents DROP COLUMN IF EXISTS checksum;
-- ALTER TABLE user_documents DROP COLUMN IF EXISTS upload_status;
-- ALTER TABLE user_documents DROP COLUMN IF EXISTS deleted_at;
