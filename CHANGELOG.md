# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] - 2026-10-17

### Added
- **Next.js App Router Frontend**: Full transition to modern React 19, Next.js 16, TypeScript, and Tailwind CSS v4, compiled as a high-performance static export for Cloudflare Workers.
- **Dual-Token Authentication Architecture**: Implemented signed HS256 Bearer token authentication alongside hardened cookies to eliminate third-party cookie restrictions across origins.
- **Dedicated Admin Control Panel (`/admin`)**: Secure server-authoritative control panel providing real Supabase metrics (user count, active sessions, message volume), student search, account suspension, and system health status.
- **5-Hour Quota Enforcement**: Server-authoritative quota policy limiting users to 30 requests per 5-hour window, replacing the legacy 8-hour window.
- **Aptivus Student Dashboard**: Integrated student dashboard featuring a 25-minute Pomodoro study sprint timer, quick-action prompt cards, and session continuity.
- **5 Calibrated Color Themes**: Distraction-free palette options (Warm Paper, Pure Light, Midnight Slate, Graphite Dark, OLED Pitch Black) designed specifically without purple tones.
- **9 Live Typography Options**: Customizable academic reading fonts (Inter, Geist, Plus Jakarta Sans, DM Sans, Manrope, IBM Plex Sans, Lora, Source Serif, JetBrains Mono).
- **Cryptographic Prompt Masking**: SHA-256 hashing applied to conversation titles and student study queries stored in Supabase to enhance privacy.
- **Mathematical & Scientific Rendering**: KaTeX math rendering support with LaTeX block and inline equation parsing.
- **Idempotent Supabase Schema**: `supabase_schema.sql` upgraded with `IF NOT EXISTS` guards and `ALTER TABLE ADD COLUMN IF NOT EXISTS` for safe schema migrations.

### Changed
- **Default Viewport**: Authenticated users now land directly in the AI chat workspace by default rather than the dashboard.
- **Cloudflare Edge Deployment**: Configured static asset hosting via `wrangler.jsonc` and `output: 'export'` in `next.config.mjs`.
- **CORS Hardening**: Centralized CORS allowed origins and explicit credentials handling for cross-domain API communication.

### Deprecated
- Legacy single-page `index.html` frontend in favor of modular Next.js components.
- Legacy 8-hour quota cycle.

### Removed
- Unused temporary files, obsolete template directories, and duplicate lockfiles.

---

## [1.0.0] - 2026-08-15

### Added
- **Telegram Bot Daemon**: Multi-provider academic study bot (`study_bot.py`) built on `python-telegram-bot` v21.9.
- **Multi-Provider AI Routing**: Dynamic routing across Groq, Gemini, DeepSeek, Cerebras, OpenRouter, SambaNova, Together, Mistral, OpenAI, and Nvidia.
- **Academic Study Modes**: Dedicated prompt modes for Socratic problem solving, theoretical deep dives (`/brainy`), multi-angle explanations (`/ask5`), formula references (`/formula`), and quiz drills (`/quiz`).
- **Live Search Grounding**: Real-time web citations powered by Tavily and DuckDuckGo search APIs.
- **Flask REST API Gateway**: Backend API (`app.py`) providing session management, authentication handshake, and CORS proxying.
- **Supabase Integration**: Cloud PostgreSQL schema for storing bot users, user memory, chat history, and quiz leaderboards.
- **Security Defenses**: Pattern blacklist, sliding-window rate limiting, and input sanitization (`security.py`).
- **Railway Deployment**: Procfile configuration running Gunicorn web service and the background Telegram daemon.
