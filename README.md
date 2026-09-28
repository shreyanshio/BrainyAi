<div align="center">
  <h1>🧠 BRAINY — AI Study Bot & Web Sanctuary</h1>

  <p>
    <a href="https://github.com/shreyanshio/BrainyAi"><img src="https://img.shields.io/badge/GitHub-Repo-181717?style=for-the-badge&logo=github&logoColor=white" alt="GitHub Repo"></a>
    <a href="https://brainyai.cenai.workers.dev"><img src="https://img.shields.io/badge/Web-Sanctuary-F59E0B?style=for-the-badge&logo=cloudflare&logoColor=black" alt="Live Web App"></a>
    <a href="https://t.me/AiChatExpert_Bot"><img src="https://img.shields.io/badge/Telegram-@AiChatExpert__Bot-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram Bot"></a>
    <a href="https://t.me/aurabreaker7"><img src="https://img.shields.io/badge/Telegram-Channel-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram Channel"></a>
    <a href="https://github.com/shreyanshio/BrainyAi/stargazers"><img src="https://img.shields.io/github/stars/shreyanshio/BrainyAi?style=for-the-badge&color=F59E0B&logo=star" alt="GitHub Stars"></a>
  </p>

  <p><strong>An executive, emotionally intelligent AI study companion built with Next.js, Cloudflare Workers, and Flask.</strong></p>
</div>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 📝 Project Description

**BRAINY** is an advanced academic intelligence platform and study companion designed for serious scholars and students. It bridges an authoritative Next.js web sanctuary with an omni-channel Telegram bot (`@AiChatExpert_Bot`), keeping memory, study streaks, and conversation sessions continuously synchronized across devices.

Powered by an intelligent multi-provider router, BRAINY directs queries to optimal models across 10+ AI providers (Groq, Gemini, DeepSeek, Cerebras, OpenAI, Mistral, OpenRouter, SambaNova, Together, and Nvidia). Whether you need step-by-step Socratic breakdowns for physics equations, real-time web search with citations, optical equation solving, or personalized revision drills, BRAINY adapts natively.

* 🌐 **Web Sanctuary:** [https://brainyai.cenai.workers.dev](https://brainyai.cenai.workers.dev)
* 🤖 **Telegram Bot:** [@AiChatExpert_Bot](https://t.me/AiChatExpert_Bot)
* 📢 **Official Channel:** [@aurabreaker7](https://t.me/aurabreaker7)
* 🔐 **Strict Authentication:** Google OAuth 2.0 & Verified Telegram Handshake (Zero Mock Bypass)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 🔧 Tech Stack & Architecture

- **Frontend:** Next.js (App Router, Tailwind CSS, Lucide Icons) deployed on **Cloudflare Workers**
- **Backend:** Python 3.10+ / Flask API with Gunicorn deployed on **Railway**
- **Telegram Daemon:** `python-telegram-bot` v21.9 running as a continuous background worker
- **Database & Sync:** Supabase (PostgreSQL with Row-Level Security)
- **AI Providers:** Groq, Gemini, DeepSeek, Cerebras, OpenAI, Mistral, OpenRouter, SambaNova, Together, Nvidia
- **Search Engine:** Tavily API + DuckDuckGo for real-time citations and factual verification
- **Deployment & Edge:** Cloudflare Workers (Frontend Static Asset Routing) & Railway (API + Bot Worker)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## ✨ Key Features

### 🤖 AI Study & Reasoning Capabilities
| Feature | Description |
|---------|-------------|
| **Multi-Provider AI** | → Intelligent routing across 10+ AI providers for optimal academic responses |
| **Socratic Problem Solving** | → Step-by-step guidance for Physics, Chemistry, and Mathematics numericals without shortcuts |
| **Deep Learning Mode** | → `/brainy` mode for comprehensive theoretical syntheses and foundational intuition |
| **5-Perspective Explanations**| → `/ask5` mode explaining tough concepts from 5 distinct pedagogical angles |
| **Vision & Image Solving** | → `/image` mode for textbook diagrams, handwritten problems, and OCR formulas |
| **Web Search & Citations** | → Real-time factual queries backed by Tavily and DuckDuckGo |
| **Adaptive Memory** | → Learns your weak topics, doubt patterns, and liked solutions automatically |

### 🌐 Web App Sanctuary Features
| Feature | Description |
|---------|-------------|
| **Obsidian & Gold UI** | → Executive high-contrast palette minimizing eye strain during long study sessions |
| **Strict Google OAuth** | → Official Google Identity Services (GIS) token verification |
| **Telegram Handshake** | → Real-time session verification linking your Telegram username and avatar |
| **Persistent History** | → Encrypted chat sessions stored and indexed in Supabase |
| **Collapsible Navigation** | → Responsive sidebar with mobile-friendly slide-over menu |
| **Syntax Highlighting** | → Prism.js formatted code blocks with one-click copy buttons |
| **Session Tools** | → Real-time search in conversation, chat export to .txt, and clipboard copy |

### 📱 Telegram Bot Features
| Feature | Description |
|---------|-------------|
| **Quizzes & Drills** | → Interactive polls with per-chat leaderboards (`/quiz`, `/leaderboard`) |
| **Flashcard Decks** | → Swipeable flashcards organized by syllabus chapter (`/flashcards`) |
| **Formula Reference** | → Subject-wise quick reference cheat sheets (`/formula`) |
| **Personal Study Plan**| → Customized 7-day adaptive study plans (`/myplan`) |
| **Bookmark Notes** | → React with 👍 to automatically save solutions to your notebook (`/mynotes`) |
| **Instant Web Login** | → Send `/login` in bot to receive pre-authenticated instant access links |

### 🔐 Security & Protection
| Feature | Description |
|---------|-------------|
| **Input Sanitization** | → Strict guards against XSS, SQLi, and Command Injection |
| **Pattern Blacklist** | → Automated detection and blocking of malicious exploit patterns |
| **Dual Rate Limiting** | → Transient per-IP and per-User rate limits to prevent resource abuse |
| **HMAC Auth Verification**| → Cryptographic verification of Telegram session tokens |
| **Hardened Cookies** | → `HttpOnly`, `Secure`, and `SameSite` cookie flags |
| **Row Level Security** | → Supabase RLS preventing cross-user data exposure |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 📁 Project Structure

```text
BrainyAi/
├── app/                           # Next.js App Router Frontend
│   ├── globals.css                # Obsidian & Gold design system tokens
│   ├── layout.tsx                 # Root layout, metadata & custom favicon
│   └── page.tsx                   # Study workspace & strict auth flow
├── prompts/                       # Modular academic prompt templates
│   ├── system_prompt.txt          # Core persona & academic formatting
│   ├── brainy_prompt.txt          # Deep reasoning mode
│   ├── quiz_prompt.txt            # MCQ drill generator
│   ├── ask5_prompt.txt            # Multi-angle explanation mode
│   └── ...                        # Specialized subject prompts
├── fonts/                         # Unicode math & scientific matrices
│   ├── math_symbols.txt           # Mathematical glyph mappings
│   ├── calculus_symbols.txt       # Integrals, limits & differential operators
│   ├── greek_letters.txt          # Greek notation rules
│   └── ...                        # Extended formatting fonts
├── public/
│   └── icon.svg                   # Custom gold & obsidian Brainy neural favicon
├── app.py                         # Flask REST API, auth handshake & CORS
├── study_bot.py                   # Telegram bot daemon & multi-provider router
├── security.py                    # Input sanitization, rate-limiting & abuse guard
├── wrangler.jsonc                 # Cloudflare Workers static asset configuration
├── next.config.mjs                # Next.js static export settings (`output: export`)
├── package.json                   # Node.js dependencies & scripts
├── requirements.txt               # Python backend dependencies
└── Procfile                       # Railway deployment entry points
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 🚀 Local Development Setup

### 1. Clone the Repository
```bash
git clone https://github.com/shreyanshio/BrainyAi.git
cd BrainyAi
```

### 2. Frontend Setup (Next.js)
```bash
# Install dependencies
npm install

# Start local Next.js dev server
npm run dev
```
The frontend will be available at `http://localhost:3000`.

### 3. Backend Setup (Python Flask & Bot)
```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate       # On Linux/macOS: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env        # Edit .env with your API keys
```

### 4. Run the Servers
```bash
# Terminal 1: Start Flask API server
python app.py

# Terminal 2: Start Telegram Bot daemon
python study_bot.py
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## ☁️ Deployment

### 1. Cloudflare Workers (Frontend)
The Next.js frontend builds to a static export (`out/`) that Cloudflare Workers serves with zero cold starts:
```bash
npm run build
npm run deploy
```

### 2. Railway (Backend & Bot Worker)
Railway automatically deploys the backend using the included `Procfile`:
* **Web Service:** `web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
* **Bot Worker:** `worker: python study_bot.py`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 👥 Contributors

<a href="https://github.com/shreyanshio/BrainyAi/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=shreyanshio/BrainyAi" />
</a>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## ⚠️ Disclaimer

**Personal Project:** This project was created for educational purposes, API testing, and personal skill development. It is **not intended for commercial or business use**. It is open-sourced purely for learning purposes.
<br>
**DATA WE STORE:-** <ul>
  <li>Telegram username-id - to assign and verify session id for web.</li>
  <li>Your chats are end-to-end encrypted, and are stored in hash values.</li>
  <li>Timestamp of chat, or time when user started the bot.</li>
  <li>Your poll responses are stored.</li>
</ul>
<br>
<b>We do not store, log, or collect any of your sensitive information or personal data, because no sensitive data ever enters or rests on our systems, there is no data to leak or breach. All data is processed in real-time and immediately discarded after use. No user messages are stored when user chats in telegram private chat.</b>
<br>
<br>
<p>BRAINY does not permanently store IP addresses in the database. User accounts, chat history, and memory are tied only to Telegram/session user IDs — never to IP addresses.
IP addresses are used only transiently, for security purposes:

Rate limiting — IPs are held briefly in server memory to detect abuse (e.g. 100 requests/minute), and cleared automatically or on server restart.
Security logging — if a request triggers abuse detection (rate-limit breach, malicious input pattern, server error), the IP is written to a local security.log file for forensic review. Normal, safe usage never generates a log entry. Limiting is not totally based on IP it also rely's on telegram userid.

No IP address is ever linked to chat content, personal data, or stored in the Supabase database.</p>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
<br>
<p>⭐ Show Your Support

If you find this project useful, please consider giving it a **Star** and **[Following](https://github.com/shreyanshio)** me on GitHub! It helps more developers discover the project and keeps me motivated to build more open-source tools.</p>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## 📬 Contact & Links

- **Creator:** Shreyansh Pathak
- **Telegram:** [@shreyanshhh_08](https://t.me/shreyanshhh_08)
- **Channel:** [@aurabreaker7](https://t.me/aurabreaker7)
- **Bot Link:** [@AiChatExpert_Bot](https://t.me/AiChatExpert_Bot)
