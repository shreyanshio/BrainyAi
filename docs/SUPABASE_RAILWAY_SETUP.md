# Supabase and Railway setup for BrainyAi

This repository already has a Flask API, a Supabase-backed data model, and a separate Google sign-in flow. The steps below extend those pieces; they do not create replacement conversation or memory tables. The new SQL migration is a proposal and has **not** been run.

## What the app currently uses

- **Backend:** Flask (`app.py`), served by Gunicorn on Railway. `study_bot.py` is the Telegram worker.
- **Database client:** direct Supabase REST/PostgREST requests with Python `requests`; there is no Supabase Python SDK in use.
- **Existing tables:** `chat_sessions` (conversation and `user_id`), `chat_messages` (message and `session_id`), `user_memory` (per-user profile, preferences, saved notes, and bot history), plus `user_logins`, `user_preferences`, `bot_users`, quiz tables, and quota/rate-limit tables. See `supabase_schema.sql` and the existing migrations.
- **Application identity:** Brainy issues its own signed session/Bearer token and stores a Brainy numeric `user_id`. Google IDs are mapped deterministically to the existing numeric ID; Telegram uses its verified Telegram user ID. These are not Supabase Auth user IDs.
- **Google sign-in:** The primary Google Identity Services button supplies an ID token. Flask verifies it with Google libraries or Google's `tokeninfo` endpoint, checks client audience, issuer, expiration and verified email, then issues a Brainy token. The existing fallback redirect still returns an OAuth access token when the GIS button fails to load; Flask now accepts that only after Google tokeninfo confirms the configured client and Google userinfo confirms the same subject and verified email. This is **not Supabase Auth**. Supabase Auth should not be enabled as a replacement unless a separate identity migration is planned, since existing records are keyed by Brainy numeric IDs.
- **Legacy web sign-in:** name-only `/api/auth/web` is allowed for local development only. It is rejected in production because a caller could impersonate another name.

## Data model and proposed migration

Reuse the existing tables:

1. `chat_sessions.user_id` remains the owner of each conversation.
2. Add `chat_messages.user_id`, backfill it from each message's parent session, and make it required. The migration stops with an explicit error if any row cannot be associated with a session owner.
3. Add a composite foreign key from `(chat_messages.session_id, chat_messages.user_id)` to `(chat_sessions.id, chat_sessions.user_id)`. This prevents a message from naming a different owner than its conversation.
4. Add/update conversation activity timestamps and indexes for per-user history ordering.
5. Add save, pin, and archive flags plus partial owner/activity indexes to the existing conversation table.
6. Keep `user_memory` as the existing per-user memory table keyed by `user_id`; do not create a second memory store.
7. Enable RLS and remove `anon`/`authenticated` table grants for `chat_sessions`, `chat_messages`, and `user_memory`. The current app does not have Supabase Auth JWTs to support `auth.uid()` policies. Browser roles receive no direct access; the trusted Railway services use the private service-role key and the Flask API filters every user-facing conversation/message query by the authenticated Brainy user ID. The composite foreign key adds a database ownership invariant.

The proposed additive migrations are [`migrations/20261018_chat_owner_integrity.sql`](../migrations/20261018_chat_owner_integrity.sql) and [`migrations/20261019_chat_workspace_metadata.sql`](../migrations/20261019_chat_workspace_metadata.sql). Do not apply them until checking the existing data and backing up the project. They do not drop tables or delete rows. The owner migration stops rather than guess if existing messages lack a parent owner. The repository also contains `migrations/20261017_durable_quotas.sql` and `migrations/20261018_chat_idempotency.sql`; those are prerequisites for current quota/rate-limit and retried-chat-write behavior.

### Safe migration review and order

1. In Supabase, confirm that this is the project currently used by Railway and inspect the existing `chat_sessions`, `chat_messages`, and `user_memory` columns and row counts.
2. Back up the project before a schema change. Review the current migration files in Git.
3. For an existing project, **do not rerun `supabase_schema.sql` blindly**. It is the repository's bootstrap schema and includes table/policy setup. First compare it with the live schema; do not create replacement tables.
4. Apply only missing, reviewed migrations in this order: `20261017_durable_quotas.sql`, `20261018_chat_idempotency.sql`, then `20261018_chat_owner_integrity.sql`. If a migration is already reflected in the live schema, verify its indexes/RPC/policies rather than running a second schema path.
5. After review and approval, run the SQL in Supabase Dashboard **SQL Editor**, one migration at a time, and inspect the result before continuing. These instructions do not run SQL for you.

## Supabase Dashboard checklist

1. Copy the **Project URL** for `SUPABASE_URL` from the project's **Connect** dialog.
2. Open **Supabase Dashboard → project → Settings → API Keys**. Create or select a private **Secret API key** (`sb_secret_...`) and copy it to `SUPABASE_SERVICE_KEY`. Supabase is moving from legacy `service_role` keys to Secret API keys; this repository supports both. The new key maps to `service_role`.
3. Keep the secret key in the Railway backend and worker variables only. It bypasses RLS. Never place it in the frontend, a `NEXT_PUBLIC_*` variable, source control, a screenshot, or a support message. Rotate it if it was exposed.
4. In **Table Editor**, verify the existing tables and their columns before any migration. Verify `chat_sessions.user_id`, and check whether every `chat_messages.session_id` points to a session. The proposed migration performs a backfill and aborts if it cannot assign an owner.
5. In **SQL Editor**, review the proposed SQL migration files and the order above. Do not execute them until the project backup and existing schema review are complete.
6. After applying approved migrations, check **Table Editor → each of `chat_sessions`, `chat_messages`, `user_memory` → RLS enabled**. Confirm there are no `anon` or `authenticated` policies or table grants for private chat/memory. Keep the service-role-only policies and grants required by the Railway service.
7. Do not enable Supabase Auth providers as a fix for Google login. The current Google flow is independently verified by Flask. Google Cloud's OAuth **Web application client ID** must match `GOOGLE_CLIENT_ID`; add the website's exact origin in Google Cloud's **Authorized JavaScript origins** and configure the same client ID in `NEXT_PUBLIC_GOOGLE_CLIENT_ID` in the frontend build environment.

The Supabase `service_role` credential is inherently powerful and bypasses RLS; table grants in the migration do not make that credential narrowly scoped. It is used here because this application authenticates Brainy identities itself. The migration blocks browser roles from the private tables, and the API must continue to authenticate each request and scope queries by owner. Replacing the service key with a custom limited PostgREST role would require a separate server-token/role design and is not part of this change.

## Railway variables

Set variables on the **web service**. Set the Supabase and Telegram variables on the **worker service** too if it runs `study_bot.py` with persistent memory/history. Railway injects `PORT` for the web service.

| Variable | Required | Purpose / handling |
|---|---|---|
| `SUPABASE_URL` | Yes for persistence | Supabase Project URL. Server-side. |
| `SUPABASE_SERVICE_KEY` | Yes for persistence | Supabase Secret API key (`sb_secret_...`), which maps to `service_role`. **Secret; server-side only.** Legacy `service_role` JWT is also supported. `SUPABASE_KEY` remains accepted as a legacy variable name. |
| `FLASK_SECRET_KEY` | Yes in production | Long random secret for signed auth/session tokens. Keep in Railway only. |
| `GOOGLE_CLIENT_ID` | If Google sign-in is offered | Google OAuth Web client ID used for backend token validation. Public identifier, not a secret. |
| `FRONTEND_URL` | Yes for production auth/origin links | Public frontend origin, e.g. `https://brainyai.cenai.workers.dev`. |
| `ALLOWED_ORIGINS` | Yes for production CORS | Comma-separated exact frontend origins. |
| `SESSION_COOKIE_SECURE` | Yes in production | `True` when using HTTPS. |
| `SESSION_COOKIE_SAMESITE` | Recommended | `None` for cross-site cookie auth, with `SESSION_COOKIE_SECURE=True`; Bearer tokens are also supported. |
| `TELEGRAM_TOKEN` | If Telegram bot/login is used | BotFather token. **Secret; web and worker server-side only.** |
| `OWNER_ID` | If Telegram admin behavior is used | Numeric Telegram owner ID. |
| `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY` | At least one provider | AI provider secrets; server-side. Optional `_1`, `_2`, etc. pool keys are supported. |
| `TAVILY_API_KEY` | Optional | Search provider secret; server-side. |
| `ADMIN_USER_IDS`, `ADMIN_USERNAMES`, `ADMIN_EMAILS` | If admin tools are needed | Comma-separated allowlists; set only intended administrators. |
| `GLOBAL_MESSAGE_LIMIT`, `QUOTA_WINDOW_HOURS` | Optional | Quota settings; defaults are 30 messages and 5 hours. |
| `API_BASE_URL` or `WEB_APP_URL` | If Telegram worker uses the web API | Public backend/API URL or web app URL used by bot links/callbacks. |
| `TELEGRAM_BOT_USERNAME` | Optional | Bot username shown to the frontend. |
| `ENVIRONMENT` or `FLASK_ENV` | Recommended | Set to `production`; Railway's `RAILWAY_SERVICE_ID` also activates production behavior. |
| `PORT` | Railway-managed | Web listener port; do not hardcode a public value. |
| `NEXT_PUBLIC_API_URL` | Frontend build only | Public Flask API base URL. This is browser-visible; never put secrets here. Configure it in the frontend build environment, not as a backend secret. |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | If Google sign-in is offered | Same Google OAuth Web client ID used by the static frontend. Public identifier, not a secret. Set in the frontend build environment. |

The code also accepts `AUTH_SECRET_KEY` or `SECRET_KEY` as fallback names for `FLASK_SECRET_KEY`; set only `FLASK_SECRET_KEY` for clarity. Do not put any secret in a variable beginning `NEXT_PUBLIC_`.

## Health, failure behavior, and checks

- Railway's configured health path is `/api/health`. It returns HTTP 200 for liveness and includes a credential-free database status (`connected`, `unconfigured`, or `unavailable`) and probe latency. Inspect `database.status`; a running process does not mean Supabase is reachable.
- Database failures are logged with operation/table/status/category and a request ID, without logging credentials or message content. Session and memory API writes return a retryable error rather than claiming the write succeeded. Chat generation can still return an answer if history persistence fails; the API response includes `persistence_warning` and `request_id` so the client can display that history was not saved.
- Rate limiting uses its independent shared RPC and a bounded local fallback during RPC trouble. It does not depend on inserting chat history.
- Run the requested local checks with `python -m unittest discover -s tests -v`. The database tests mock PostgREST; they verify request scoping, save/reload contracts, health status, and auth behavior without accessing a real Supabase project. A real RLS check requires a staging project and should use non-production accounts after the migration is reviewed and applied.
## Additive chat workspace migration

The chat workspace uses the existing `public.chat_sessions` table. It does not
create replacement conversation/message tables. In Supabase Dashboard, open
**SQL Editor → New query**, review and apply migrations in this order if they
have not already been applied:

1. `migrations/20261017_durable_quotas.sql`
2. `migrations/20261018_chat_idempotency.sql`
3. `migrations/20261018_chat_owner_integrity.sql`
4. `migrations/20261019_chat_workspace_metadata.sql`

The workspace migration only adds `is_saved`, `is_pinned`, and `is_archived`
columns and partial owner/activity indexes. It preserves existing records.
Verify with `select column_name from information_schema.columns where table_schema
= 'public' and table_name = 'chat_sessions' and column_name in
('is_saved','is_pinned','is_archived');`. Keep the existing service-role policy
and keep the Supabase secret key only in the Railway backend service variables.
The application does not apply migrations or deploy them automatically.
