# Reliability contracts

## Chat streaming

`POST /api/chat/stream` returns newline-delimited JSON events: `start` (including a request ID), `status`, `delta`, then `done` or `error`. The browser reads through the final unterminated line and keeps partial output visible after an interruption. Safe error responses and server diagnostics carry a request ID; logs record the ID and failure category without conversation text.

Chat history writes are best effort for answer delivery. A generated answer is still streamed if saving the user message, creating a new session, saving the assistant message, or renaming the session fails. A `done.persistence_warning` flag tells the UI to show that the conversation may not have been saved. The message row idempotency key is scoped to a session; apply `migrations/20261018_chat_idempotency.sql` before relying on idempotent retries. The migration stops if existing duplicate keys need review.

## Limits and quotas

The API enforces an IP abuse limit (100 requests/minute), a per-user chat limit (10 messages/minute), a separate per-user search limit (5 searches/minute), and the existing durable product quota (30 messages per 5-hour window by default). The first three use the atomic `brainy_check_rate_limit` Supabase RPC; product quota uses its own atomic consume/refund RPC. Production returns a controlled 503 if those shared operations are missing or unavailable. It never falls back to process-local counters in production. Local development can still use in-process fallback counters. The current IP key uses Flask's `request.remote_addr` and intentionally ignores untrusted forwarding headers; configure trusted proxy handling at the deployment boundary if the host does not provide the client address as the socket peer.

Apply `migrations/20261017_durable_quotas.sql` to the configured Supabase project and set `SUPABASE_URL` and a private service-role key (`SUPABASE_SERVICE_KEY` or the existing `SUPABASE_KEY`) on the backend. Treat the key as secret. Configure `ENVIRONMENT=production` or `FLASK_ENV=production` on Railway so missing shared rate-limit credentials fail closed.

## Search

Tavily remains the configured full-search provider. If unavailable, Brainy calls DuckDuckGo Instant Answer JSON, which can provide an abstract, answer, definition, or related topic for supported queries. It is not a full search API. Brainy no longer scrapes DuckDuckGo HTML; no useful Instant Answer yields a direct no-result notice, without claiming a full web search occurred. Only HTTP(S) source URLs returned by a provider are passed on.

## Typography and sign-in

Lora is loaded through the existing Google Fonts stylesheet and is the application-wide default, including the login experience and existing saved preference records. Monospace code remains JetBrains Mono. The sign-in hero uses a CSS 3D study-card scene that follows pointer movement and disables motion when the user requests reduced motion. Google and Telegram continue to use the existing backend authentication flows.

## Verification

Run `python -m unittest discover -s tests -v` for mocked backend contract tests and `npm run build` for the frontend type check and production build. Supabase migrations and real provider/auth flows still require an isolated configured integration environment; build and mocked tests do not verify production credentials or database behavior.
