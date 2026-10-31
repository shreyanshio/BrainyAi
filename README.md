<div align="center">
  <img
    src="https://res.cloudinary.com/dtz0urit6/image/upload/e_trim,c_limit,w_360,q_auto:best,f_jpg/cloudinary-tools-uploads/xtjfsglkkem4xjxhkqzh"
    alt="Brainy AI logo"
    width="144"
  />

  <h1>BRAINY AI</h1>
  <p><strong>Your AI-powered study companion.</strong></p>

  <p>
    <a href="https://brainyai.cenai.workers.dev/"><strong>🌐 Open Web App</strong></a>
    &nbsp; · &nbsp;
    <a href="https://t.me/AiChatExpert_Bot"><strong>✈️ Open Telegram Bot</strong></a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/Next.js-16-000000?logo=next.js&logoColor=white" alt="Next.js 16" />
    <img src="https://img.shields.io/badge/React-19-149ECA?logo=react&logoColor=white" alt="React 19" />
    <img src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white" alt="Python 3.10+" />
    <img src="https://img.shields.io/badge/License-MIT-2E8B57" alt="MIT License" />
  </p>
</div>

---

## What is Brainy AI?

Brainy AI is an AI-powered learning workspace that helps students understand concepts, explore ideas, and keep their study workflow in one place — on the web and through Telegram.

## What you can do

| Feature | What it offers |
|:--|:--|
| **AI Study Chat** | Ask questions and get clear, study-focused explanations. |
| **Multi-Provider AI** | Uses the configured AI providers with routing and fallback support. |
| **PDF Study Studio** | Work with study documents and turn learning material into study resources. |
| **Telegram Study Bot** | Access study assistance and learning tools directly in Telegram. |
| **Search-Enabled Answers** | Retrieve relevant information from connected search providers. |
| **Personal Workspace** | Keep conversations and study activity organized. |

## Built with

| Part | Technologies |
|:--|:--|
| **Frontend** | Next.js · React · TypeScript · Tailwind CSS |
| **Backend** | Python · Flask |
| **Database & Auth** | Supabase · PostgreSQL |
| **AI & Search** | Configurable AI providers · Tavily · DuckDuckGo |
| **Telegram** | Python Telegram Bot |

## How it fits together

```mermaid
flowchart LR
    W["Web App"] --> API["Brainy AI Backend"]
    T["Telegram Bot"] --> API
    API --> AI["AI Providers"]
    API --> DB[("Supabase")]
    API --> S["Search Providers"]
```

## Project structure

| Directory / file | Purpose |
|:--|:--|
| `app/` · `components/` | Web application and UI components |
| `ai_routing/` | AI provider routing |
| `pdf_studio/` | PDF study features |
| `prompts/` | AI prompts |
| `study_bot.py` | Telegram bot |
| `app.py` | Python backend API |

## Explore Brainy AI

<div align="center">
  <a href="https://brainyai.cenai.workers.dev/"><strong>Launch Brainy AI ↗</strong></a>
  &nbsp; · &nbsp;
  <a href="https://t.me/AiChatExpert_Bot"><strong>Chat on Telegram ↗</strong></a>
  &nbsp; · &nbsp;
  <a href="https://github.com/shreyanshio/BrainyAi"><strong>View on GitHub ↗</strong></a>
</div>

## Contributing

Suggestions, bug reports, and pull requests are welcome. Open an issue to discuss an idea or report a problem.

## License

Released under the [MIT License](LICENSE).
