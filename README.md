<div align="center">
  <img
    src="https://res.cloudinary.com/dtz0urit6/image/upload/e_trim,c_limit,w_360,q_auto:best,f_png/cloudinary-tools-uploads/xtjfsglkkem4xjxhkqzh"
    alt="Brainy AI logo"
    width="136"
  />

  <h1>BRAINY AI</h1>
  <p><strong>Your AI-powered study companion.</strong></p>

  <p>
    <a href="https://brainyai.cenai.workers.dev/">
      <img src="https://img.shields.io/badge/OPEN%20WEB%20APP-Cloudflare-F38020?style=for-the-badge&logo=cloudflare&logoColor=white" alt="Open Brainy AI web app" />
    </a>
    &nbsp;
    <a href="https://t.me/AiChatExpert_Bot">
      <img src="https://img.shields.io/badge/OPEN%20TELEGRAM%20BOT-26A5E4?style=for-the-badge&logo=telegram&logoColor=white" alt="Open Brainy AI Telegram bot" />
    </a>
    &nbsp;
    <a href="https://github.com/shreyanshio/BrainyAi">
      <img src="https://img.shields.io/badge/SOURCE%20CODE-181717?style=for-the-badge&logo=github&logoColor=white" alt="View source code on GitHub" />
    </a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/Next.js-000000?style=flat-square&logo=nextdotjs&logoColor=white" alt="Next.js" />
    <img src="https://img.shields.io/badge/React-149ECA?style=flat-square&logo=react&logoColor=white" alt="React" />
    <img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript" />
    <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
    <img src="https://img.shields.io/badge/Supabase-3FCF8E?style=flat-square&logo=supabase&logoColor=white" alt="Supabase" />
    <img src="https://img.shields.io/badge/Cloudflare-F38020?style=flat-square&logo=cloudflare&logoColor=white" alt="Cloudflare" />
  </p>
</div>

---

## What is Brainy AI?

An AI-powered learning workspace for understanding concepts, exploring ideas, and keeping study activity organized — available on the web and through Telegram.

## Features

| | Feature | |
|:--:|:--|:--|
| <img src="https://cdn.simpleicons.org/openai/412991" width="22" alt="AI" /> | **AI Study Chat** | Study-focused explanations and guided problem solving. |
| <img src="https://cdn.simpleicons.org/stackblitz/1389FD" width="22" alt="Routing" /> | **Multi-Provider AI** | Configurable model routing and provider fallback. |
| <img src="https://cdn.simpleicons.org/adobeacrobatreader/EC1C24" width="22" alt="PDF" /> | **PDF Study Studio** | Work with learning documents and study resources. |
| <img src="https://cdn.simpleicons.org/telegram/26A5E4" width="22" alt="Telegram" /> | **Telegram Bot** | Take study assistance and learning tools into Telegram. |
| <img src="https://cdn.simpleicons.org/duckduckgo/DE5833" width="22" alt="Search" /> | **Search-Enabled Answers** | Connect answers to live search providers. |
| <img src="https://cdn.simpleicons.org/supabase/3FCF8E" width="22" alt="Workspace" /> | **Personal Workspace** | Keep conversations and study activity together. |

## Technology

<p>
  <img src="https://img.shields.io/badge/Next.js-000000?style=flat-square&logo=nextdotjs&logoColor=white" alt="Next.js" />
  <img src="https://img.shields.io/badge/React-149ECA?style=flat-square&logo=react&logoColor=white" alt="React" />
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript" />
  <img src="https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white" alt="Tailwind CSS" />
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Flask-000000?style=flat-square&logo=flask&logoColor=white" alt="Flask" />
  <img src="https://img.shields.io/badge/Supabase-3FCF8E?style=flat-square&logo=supabase&logoColor=white" alt="Supabase" />
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/Cloudflare-F38020?style=flat-square&logo=cloudflare&logoColor=white" alt="Cloudflare" />
  <img src="https://img.shields.io/badge/Telegram-26A5E4?style=flat-square&logo=telegram&logoColor=white" alt="Telegram" />
</p>

| Layer | Stack |
|:--|:--|
| **Web** | Next.js · React · TypeScript · Tailwind CSS |
| **API** | Python · Flask |
| **Data & Auth** | Supabase · PostgreSQL |
| **AI & Search** | Configured AI providers · Tavily · DuckDuckGo |
| **Messaging** | Telegram Bot API |

## Security & privacy

Brainy AI includes application-level security controls in its backend:

- **Signed authentication:** HMAC-SHA256-signed bearer tokens with signature and expiry validation.
- **Session protection:** HTTP-only and Secure cookie settings, with configurable SameSite behavior.
- **Cross-origin checks:** Configured CORS origin allowlist and Origin/Referer validation for cookie-authenticated write requests.
- **Abuse controls:** IP-based request rate limiting, with shared Supabase-backed counters when configured.
- **Admin access control:** Admin privileges are checked server-side against configured user ID, username, and email allowlists.
- **Security headers:** Content Security Policy, HSTS in production, MIME-sniffing protection, referrer policy, and restricted browser permissions.
- **Safer API caching:** Sensitive API responses are marked private and non-cacheable.
- **Production login rules:** Unverified name-only login is disabled in production.

> **Security note:** These safeguards do not mean the application is breach-proof or independently certified. Production security also depends on deployment settings, secret management, dependency updates, and correctly configured Supabase table policies. Keep service-role keys and all provider credentials on the server — never in frontend code. No independent security audit is currently claimed.

## Architecture

```mermaid
flowchart LR
    W["Web App"] --> API["Brainy AI Backend"]
    T["Telegram Bot"] --> API
    API --> AI["AI Providers"]
    API --> DB[("Supabase")]
    API --> S["Search Providers"]
```

## Project structure

| Path | Purpose |
|:--|:--|
| `app/` · `components/` | Web application and UI |
| `ai_routing/` | AI provider routing |
| `pdf_studio/` | PDF study features |
| `prompts/` | AI prompts |
| `study_bot.py` | Telegram bot |
| `app.py` · `security.py` | Backend API and security controls |

## Contributing

Ideas, bug reports, and pull requests are welcome. Open an issue to start a discussion.

## License

[MIT License](LICENSE)
