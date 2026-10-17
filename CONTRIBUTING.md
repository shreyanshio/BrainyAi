# Contributing to Brainy AI

Thank you for your interest in contributing to **Brainy AI**! Brainy is an open-source, multi-provider AI study companion and SaaS platform built for students worldwide.

---

## 1. Project Architecture

The repository is structured into two main layers:

```
BrainyAi/
├── app/                  # Next.js App Router (TypeScript, React, Tailwind CSS)
│   ├── admin/            # Secure /admin Control Panel
│   ├── page.tsx          # Main Study Sanctuary Shell
│   ├── layout.tsx        # HTML Root Layout & Metadata
│   └── globals.css       # Design System Tokens & 5 Calibrated Themes
├── components/           # Modular React Components
│   ├── app-shell/        # Header, Sidebar, Segmented Switchers
│   ├── auth/             # LoginView (Google OAuth, Telegram, 1-Click Pass)
│   ├── chat/             # MessageList, Composer, EmptyState
│   ├── dashboard/        # StudentDashboard, Pomodoro Focus Timer, Bento Cards
│   ├── modals/           # UsageModal (5-Hour Quota), NotesModal
│   └── settings/         # SettingsModal (Typography, Theme, Accent Picker)
├── lib/                  # Utilities & API Clients
│   ├── api.ts            # Typed REST Client with Bearer Token Storage
│   └── constants.ts      # Models, Themes, Accents, Font Options
├── types/                # Unified TypeScript Data Contracts (types/api.ts)
├── app.py                # Flask REST API Gateway & Authorization Service
├── security.py           # HS256 Token Auth, Rate Limiter, Input Sanitization
├── study_bot.py          # Multi-Provider AI Routing, Prompt Engineering & Supabase Client
├── supabase_schema.sql   # Production PostgreSQL Database Schema & RLS Policies
├── package.json          # Frontend Dependencies & Build Scripts
└── requirements.txt      # Python Backend Dependencies
```

---

## 2. Local Development Setup

### Prerequisites
- **Node.js**: v18.17 or later
- **Python**: 3.10 or later
- **Git**

### Step-by-Step Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/shreyanshio/BrainyAi.git
   cd BrainyAi
   ```

2. **Backend Setup**:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate

   pip install -r requirements.txt
   ```

3. **Frontend Setup**:
   ```bash
   npm install
   ```

4. **Configure Environment Variables**:
   ```bash
   cp .env.example .env
   # Populate SUPABASE_URL, SUPABASE_KEY, GROQ_API_KEY, etc.
   ```

5. **Run the Services**:
   - Backend:
     ```bash
     python app.py
     ```
   - Frontend:
     ```bash
     npm run dev
     ```

---

## 3. Verification & Testing

Before submitting a Pull Request, always verify that your code passes all type checks and compiles cleanly:

```bash
# 1. Verify Python files compile with 0 syntax or import errors
python -m py_compile app.py security.py study_bot.py

# 2. Verify Next.js production build and TypeScript checks pass
npm run build
```

---

## 4. Code Standards & Guidelines

- **Zero Purple Shades**: Brainy enforces an academic, distraction-free aesthetic with emerald, sapphire, amber, and graphite accents. Avoid introducing purple or lavender visual tokens.
- **Server Authority**: Quotas, rate limits, and access controls must always be validated server-side.
- **Privacy First**: Sensitive student queries and conversation titles must remain protected and never logged in plaintext.
- **Maintain Comments**: Preserve existing documentation and docstrings across modified files.

---

## 5. Submitting a Pull Request

1. Create a descriptive feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Commit your changes with a clear message:
   ```bash
   git commit -m "feat(chat): improve mathematical formula rendering"
   ```
3. Push to your branch and open a Pull Request on GitHub against `main`.
