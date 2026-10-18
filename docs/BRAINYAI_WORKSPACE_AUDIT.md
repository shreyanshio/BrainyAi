# BrainyAi persistence and workspace audit

**Audit date:** 2026-10-18  
**Scope:** Existing chat, authentication, Supabase, context, and workspace paths.

## Architecture and request flow

- The frontend is Next.js 16 with React 19 and TypeScript. Chat UI and workspace state live in `app/page.tsx`; the sidebar is `components/app-shell/Sidebar.tsx`; API calls are centralized in `lib/api.ts`.
- The web API is Flask (`app.py`). It validates the existing Brainy session and derives the numeric `user_id` server-side. Google Identity Services is integrated as a separate Google token verification/login flow; this is not Supabase Auth. Telegram login is also supported. This upgrade preserves these identities and session cookies.
- The Python service uses Supabase PostgREST through `requests` and a server-side key. It does not use the Supabase JS/Python SDK. Chat data already lives in `chat_sessions` and `chat_messages`; user profile/preferences/notes live in the existing `user_memory` and `user_preferences` tables.
- Send flow: frontend sends to Flask (including the stable chat ID where available); Flask authenticates the Brainy session, verifies session ownership, loads that conversation's messages from Supabase, calls the existing AI provider path, and stores messages. Streaming has an analogous path. The current chat history loader returns a conversation's messages in ID order, and the prompt receives same-chat history. The server does not mix chat IDs.

## Existing protections and behavior

- Conversation and message access is scoped by the authenticated user's numeric ID in backend queries. Existing additive migrations include message ownership, a composite owner/session relationship, activity timestamps, message idempotency, and server-only service-role RLS policies. The main schema also enables RLS.
- Supabase is the durable source when configured. In-memory maps remain for development fallback; they are not durable and must not be used as production persistence.
- The frontend fetches conversation metadata at login, fetches full history only on opening a chat, and remembers the selected chat ID locally for restoration. Renaming/deleting already call the API.
- Same-chat context currently loads the full persisted conversation in stable pages, so it grows without a context budget or rolling summary. This preserves context for normal chats but can exceed provider context limits on very long chats.
- The sidebar currently offers recent chats, rename, delete, and title-only local search. Save/pin/archive metadata and workspace views were missing. Delete previously had no confirmation.
- Long-term user data currently uses the existing `user_memory` JSON fields and notes/preferences endpoints. There is no dedicated opt-in cross-chat memory setting/workflow in this change. Existing chat history remains separate from saved notes.

## Risks and migration assumptions

- The REST service key bypasses user-facing RLS, so ownership filters in every backend operation remain essential. Never put that key in frontend variables.
- `migrations/20261018_chat_owner_integrity.sql` is the owner-integrity prerequisite; `migrations/20261018_chat_idempotency.sql` adds retry identifiers. Do not recreate chat tables.
- The migration in this upgrade only adds nullable/defaulted workspace metadata and indexes to `chat_sessions`. Existing rows and messages are preserved. Apply migrations in the documented order in Supabase SQL Editor after review; this repository does not apply them automatically.
- Full-text message search, context summarization, and user-controlled long-term memory management require additional design and are not claimed as implemented by this workspace metadata change.

## Implementation order

1. Add a versioned, additive migration for saved, pinned, and archived state on the existing conversation table.
2. Expose owner-scoped metadata updates and list those flags through the existing Flask session endpoints.
3. Add persistent Saved, Pinned, and Archived filters and controls to the existing sidebar; confirm permanent deletion.
4. Verify API/UI build and regression tests. Apply the SQL and deploy only after review.

