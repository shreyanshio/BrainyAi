# Contributing to Brainy AI

Thank you for your interest in contributing to **Brainy AI**! Brainy is an open-source, multi-provider AI study companion and academic SaaS platform built to help students understand complex concepts, solve problems, and structure their learning.

We welcome contributions from developers, technical writers, designers, and students of all experience levels.

---

## 1. Code of Conduct

All contributors and participants are expected to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before participating in discussions or submitting pull requests.

---

## 2. Project Architecture & Directory Layout

Brainy AI is organized into a modular architecture combining a Next.js static edge frontend, a Python Flask API gateway, an asynchronous Telegram bot worker, and Supabase PostgreSQL:

```text
BrainyAi/
├── app/                           # Next.js App Router (React 19, TypeScript)
│   ├── admin/                     # Secure /admin Control Panel
│   ├── globals.css                # CSS variables, Tailwind tokens & 5 theme definitions
│   ├── layout.tsx                 # Root layout, HTML headers & favicon
│   └── page.tsx                   # Study chat workspace & core application shell
├── components/                    # Modular React Components
│   ├── app-shell/                 # AppHeader, Sidebar, navigation switchers
│   ├── auth/                      # LoginView (Google OAuth, Telegram, 1-Click Pass)
│   ├── chat/                      # MessageList, Composer, EmptyState
│   ├── dashboard/                 # StudentDashboard, Pomodoro Focus Timer, Bento Cards
│   ├── markdown/                  # MarkdownRenderer with KaTeX LaTeX equation parsing
│   ├── modals/                    # UsageModal (5-Hour Quota), NotesModal
│   └── settings/                  # SettingsModal (Typography, Theme, Accent Picker)
├── docs/                          # Specialized Technical Documentation
│   ├── API.md                     # Authoritative REST API reference
│   ├── ARCHITECTURE.md            # System topology, trust boundaries & sequence diagrams
│   ├── DATABASE.md                # Supabase schema, table specs & RLS policies
│   └── DEPLOYMENT.md              # Cloudflare Workers & Railway deployment guide
├── fonts/                         # Math symbols, Greek letters & unicode reference matrices
├── lib/                           # Typed REST API clients & constants
├── prompts/                       # Academic system prompt templates (Socratic, deep learning)
├── public/                        # Static assets (icon.svg)
├── types/                         # Unified TypeScript data contracts
├── app.py                         # Flask REST API gateway & admin endpoints
├── security.py                    # HS256 JWT auth, rate limiter & input sanitization
├── study_bot.py                   # Telegram bot daemon & multi-provider router
├── supabase_schema.sql            # Idempotent PostgreSQL schema with RLS policies
├── wrangler.jsonc                 # Cloudflare Workers static export configuration
├── next.config.mjs                # Next.js static export settings (`output: 'export'`)
├── package.json                   # Frontend dependencies and scripts
└── requirements.txt               # Python backend dependencies
```

---

## 3. Local Development Setup

### Prerequisites
* **Node.js**: v18.17 or higher
* **Python**: v3.10 or higher
* **Git**
* A free [Supabase](https://supabase.com) project for relational database storage.
* At least one AI provider API key (e.g., [Groq](https://groq.com) or [Google AI Studio](https://aistudio.google.com)).

### Step-by-Step Instructions

1. **Fork and Clone**:
   ```bash
   git clone https://github.com/your-username/BrainyAi.git
   cd BrainyAi
   ```

2. **Configure Environment Variables**:
   ```bash
   cp .env.example .env
   # Open .env and populate FLASK_SECRET_KEY, SUPABASE_URL, SUPABASE_KEY, GROQ_API_KEY, etc.
   ```

3. **Backend Setup (Python Virtual Environment)**:
   ```bash
   # Create and activate virtual environment
   python -m venv venv

   # On Windows:
   .\venv\Scripts\activate
   # On macOS / Linux:
   source venv/bin/activate

   # Install dependencies
   pip install -r requirements.txt
   ```

4. **Frontend Setup (Node.js)**:
   ```bash
   npm install
   ```

5. **Initialize Database Schema**:
   In your Supabase project's **SQL Editor**, run the contents of [`supabase_schema.sql`](supabase_schema.sql).

6. **Start the Development Servers**:
   * **Terminal 1 (Flask API Gateway)**:
     ```bash
     python app.py
     ```
     The backend starts at `http://localhost:5000`.
   * **Terminal 2 (Next.js Frontend)**:
     ```bash
     npm run dev
     ```
     The frontend starts at `http://localhost:3000`.
   * **Terminal 3 (Optional — Telegram Bot Worker)**:
     ```bash
     python study_bot.py
     ```

---

## 4. Development Standards & Guidelines

### A. Design System & Theme Rules
* **Zero Purple Shades**: Brainy enforces a distraction-free, focused academic palette based on warm paper, slate, emerald, and dark graphite tones. **Do not introduce purple or lavender colors into the user interface.**
* **Accessibility**: Maintain a minimum contrast ratio of 4.5:1 for body copy across all 5 themes.

### B. Security & Server Authority
* **Server-Authoritative Enforcement**: Message quotas (30 messages per 5 hours), rate limits (10 req/min), and admin access must always be validated and enforced by the server. Never trust client-reported counts.
* **Privacy by Design**: Sensitive user queries and chat titles must remain masked with SHA-256 hashes before insertion into Supabase.
* **Secret Protection**: Never commit API keys, bot tokens, service-role keys, or private environment files to Git.

### C. Code Quality & Formatting
* **TypeScript**: Use strict typing. Avoid `any` types; define data structures in `types/api.ts`.
* **Python**: Follow PEP 8 guidelines. Keep functions modular and maintain docstrings and explanatory comments.
* **Documentation Integrity**: Preserve existing comments that explain non-obvious design decisions.

---

## 5. Verification Commands

Before opening a pull request, ensure all validation checks pass locally:

```bash
# 1. Verify Python files compile with zero syntax errors
python -m py_compile app.py security.py study_bot.py

# 2. Run TypeScript checks and production Next.js build
npm run build
```

---

## 6. Commit Message Guidelines

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

* `feat(chat): add KaTeX rendering for multiline equation blocks`
* `fix(auth): resolve cross-origin bearer token synchronization`
* `docs(api): document administrative health endpoints`
* `refactor(routing): streamline fallback provider list in study_bot`
* `test(quota): verify 5-hour window calculation`

---

## 7. Submitting a Pull Request

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. Make your changes and commit them cleanly.
3. Run the verification commands listed above.
4. Push your branch to your GitHub fork:
   ```bash
   git push origin feat/your-feature-name
   ```
5. Open a Pull Request against `shreyanshio/BrainyAi:main` using our [Pull Request Template](.github/PULL_REQUEST_TEMPLATE.md).
6. A maintainer will review your pull request, provide feedback, and merge when ready.
