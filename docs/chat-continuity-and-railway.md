# Chat continuity and Railway rollout

## What the repository uses

- The web frontend is Next.js/React. Chat selection and streaming UI live in `app/page.tsx` and `lib/api.ts`.
- The web API is Flask in `app.py`. It calls Supabase through server-side PostgREST requests (`requests`), not a browser Supabase client.
- Chat data uses the existing `public.chat_sessions`, `public.chat_messages`, and `public.user_memory` tables. The continuity migration adds columns to `chat_sessions`; it creates no replacement chat tables.
- Google login is the existing Google Identity Services flow. The browser sends a Google credential to Flask; Flask verifies it and establishes Brainy’s own signed session/token. It is not Supabase Auth. This change keeps that flow intact. The backend’s numeric Brainy user ID remains the owner ID for chat rows.
- Session and message reads/writes filter by the authenticated Brainy user ID. Message history also filters by the selected session ID. The existing owner-integrity migration enables RLS on the three private tables, grants CRUD to `service_role`, and revokes table privileges from `public`, `anon`, and `authenticated`; the application adds owner filters because its signed Brainy identity is not a Supabase Auth JWT.

## Root causes addressed

1. Startup converted a failed session-list request into `[]`, making a database/network error look like an account with no chats.
2. Selecting a chat changed the active ID before loading its messages, left the previous chat’s messages on screen, and did not guard against out-of-order fetches. A failed or slow request could show the wrong transcript under the selected title.
3. The sidebar query stopped at 100 sessions and had no older-page control. Restoring the last active chat also depended on that first page.
4. If a history query failed, the backend continued with only the latest question. That made a follow-up look like a new chat. It now returns a retryable storage error and refunds the consumed quota.
5. User questions and titles are stored in the existing `hsh_v1_` encrypted format. A key mismatch previously returned that encoded payload as if it were readable text. Decryption now tries the current and explicitly configured previous keys, then fails closed without exposing ciphertext.
6. The Groq streaming routes referred to `llama-3.1-8b-instant` and `llama-3.3-70b-versatile`, which Groq documents as decommissioned on August 16, 2026. The new defaults are configurable active Groq models.

The backend already loaded same-session history from Supabase and passed it to the model. The failure case was history-read degradation and content that could not be decrypted; longer chats also had no durable summary.

## Supabase migration

Review and apply `migrations/20261020_chat_context_summary.sql` in the Supabase SQL Editor **after confirming the existing chat tables and the earlier owner-integrity migrations are present**. It adds three nullable summary fields to the existing sessions table and does not delete or rewrite user records.

The backend detects an unapplied summary migration and falls back to the existing full-history behavior. Once the columns are present, it encrypts rolling summaries, stores the highest message ID represented by each summary, and uses the summary plus newer messages as model context. A background task performs summary work after responses; it does not delay the stream. Summary reads and writes are owner-filtered. Do not disable RLS or grant `anon`/`authenticated` public access to private chat data.

Existing migrations in this repository, in order, are:

1. `migrations/20261017_durable_quotas.sql`
2. `migrations/20261018_chat_owner_integrity.sql`
3. `migrations/20261018_chat_idempotency.sql`
4. `migrations/20261019_chat_workspace_metadata.sql`
5. `migrations/20261020_chat_context_summary.sql`

Do not rerun migrations blindly. Check `information_schema.columns`, `pg_policies`, and table grants first. No SQL was executed by this change.

## Railway and frontend variables

Set backend variables in Railway’s **BrainyAi Flask service**:

| Variable | Purpose | Secret? |
| --- | --- | --- |
| `SUPABASE_URL` | Project URL used by Flask and the bot | No |
| `SUPABASE_SERVICE_KEY` | Server-side PostgREST access for the backend | **Yes; never put in frontend/build variables** |
| `AUTH_SECRET_KEY` | Stable Brainy session signing and existing chat-content encryption key | **Yes; keep stable across deploys** |
| `GOOGLE_CLIENT_ID` | Google credential audience verified by Flask | No |
| `GROQ_API_KEY` | Groq provider key; optionally numbered `GROQ_API_KEY_1` through `_10` | **Yes** |
| `GROQ_MODEL_FAST` | Optional model override; defaults to `openai/gpt-oss-20b` | No |
| `GROQ_MODEL_BALANCED` | Optional model override; defaults to `openai/gpt-oss-120b` | No |
| `CHAT_ENCRYPTION_PREVIOUS_KEYS` | Optional comma-separated old content keys during/after a key rotation | **Yes; only add old keys actually used for stored content** |
| `FRONTEND_URL` | Public frontend origin used by auth/redirect flows | No |
| `ALLOWED_ORIGINS` | Comma-separated allowed browser origins for Flask CORS | No |

`SUPABASE_KEY` and `SECRET_KEY`/`FLASK_SECRET_KEY` are legacy aliases in code. Prefer `SUPABASE_SERVICE_KEY` and `AUTH_SECRET_KEY`, and keep the signing/encryption key stable. The new `CHAT_ENCRYPTION_PREVIOUS_KEYS` option is for historical decryption only; keep old keys until every record encrypted with them has been deliberately re-encrypted.

For a separately hosted Next.js frontend, configure these in the frontend host’s build environment, not as backend secrets:

- `NEXT_PUBLIC_API_URL`: Flask/Railway API URL.
- `NEXT_PUBLIC_GOOGLE_CLIENT_ID`: the same OAuth client ID configured as backend `GOOGLE_CLIENT_ID`. This is a public client ID, not a secret.

`TELEGRAM_TOKEN` is needed only if the Telegram bot runs in this Railway service. `API_BASE_URL` and `WEB_APP_URL` are for Telegram links. Any provider keys for Gemini, OpenRouter, Cerebras, or other existing fallbacks stay server-side.

## Manual rollout checklist

1. In Railway, set the backend variables above. Preserve the existing `AUTH_SECRET_KEY`; if it has already changed, set `CHAT_ENCRYPTION_PREVIOUS_KEYS` to the old key(s) without printing them into chat, code, logs, or Git.
2. In Supabase **Project Settings → API**, copy the project URL and server-side service key into Railway only. Do not put a service-role/secret key in Next.js variables.
3. Supabase **Authentication → Providers → Google** is not used by this repository’s current sign-in. In **Google Cloud Console → APIs & Services → Credentials**, keep the existing Google Identity Services OAuth client and add the production frontend origin under its authorized JavaScript origins. Set that client ID in both frontend and Flask. No Supabase OAuth callback is needed unless the app is intentionally migrated to Supabase Auth later.
4. In Supabase **SQL Editor**, inspect the existing tables, RLS policies, and privileges. Apply the owner-integrity/idempotency/workspace migrations only if they are not already present and the existing schema matches. Then review and apply `20261020_chat_context_summary.sql`.
5. In Supabase **Table Editor → chat_sessions/chat_messages**, confirm RLS is enabled and policies/grants do not allow public reads. The application service key is private and performs explicit owner filters in Flask.
6. In Railway, set the health-check path to `/api/health`. Confirm it reports `database.status: connected` after deploying the backend.
7. Redeploy manually after reviewing the code and SQL. Test Google login, open a chat beyond the first sidebar page, continue it, refresh, and verify its order and saved/pinned metadata.

## Streaming and measurements

Authentication and request-security validation are measured separately from the route pipeline, so the total server-side duration can be reconstructed without logging request content.

The browser now coalesces token deltas into short batches to avoid reparsing/rendering the whole Markdown transcript for each token while still painting the first token immediately. The API records authentication validation, ownership lookup, history read, context assembly, model time-to-first-token, generation, persistence, and total durations. Logs contain request IDs, stage durations, routing model ID, and message counts, not conversation text or keys.

Groq’s model pages list approximately 1,000 tokens/second and $0.075/$0.30 per million input/output tokens for `openai/gpt-oss-20b`, and approximately 500 tokens/second and $0.15/$0.60 per million for `openai/gpt-oss-120b`. Those provider throughput figures are not Brainy end-to-end latency promises, and these are paid model prices rather than a claim of free availability. Current model IDs, quotas, and prices can change; check [Groq model docs](https://console.groq.com/docs/models) and [Groq deprecations](https://console.groq.com/docs/deprecations) before changing production routing.

The repository environment used for local checks did not have AI provider or Supabase credentials configured. Therefore no live provider TTFT, Supabase latency, or before/after production p50/p95 can be truthfully reported from this checkout. The added tests mock provider/database calls and verify contracts; they do not certify Railway connectivity or answer quality.
