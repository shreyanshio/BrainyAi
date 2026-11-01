<div align="center">
  <a href="https://brainyai.cenai.workers.dev/">
    <img src="./public/brand/brainy-web-desktop.png" alt="Brainy — AI Study Companion" width="420" />
  </a>

  <h3>Think it through. Learn it properly.</h3>
  <p>An AI study companion for curious minds — built for everyday questions, deeper explanations, and more active learning.</p>

  <p>
    <a href="https://brainyai.cenai.workers.dev/"><img src="https://img.shields.io/badge/OPEN_WEB_APP-0D8B67?style=for-the-badge&logo=googlechrome&logoColor=white" alt="Open Web App" /></a>
    <a href="https://t.me/AiChatExpert_Bot"><img src="https://img.shields.io/badge/TRY_ON_TELEGRAM-229ED9?style=for-the-badge&logo=telegram&logoColor=white" alt="Try on Telegram" /></a>
    <a href="https://github.com/shreyanshio/BrainyAi"><img src="https://img.shields.io/badge/STAR_ON_GITHUB-24292F?style=for-the-badge&logo=github&logoColor=white" alt="Star on GitHub" /></a>
    <a href="https://github.com/shreyanshio/BrainyAi/issues/new"><img src="https://img.shields.io/badge/REPORT_A_BUG-EA4335?style=for-the-badge&logo=github&logoColor=white" alt="Report a bug" /></a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/Next.js-16-black?logo=nextdotjs" alt="Next.js" />
    <img src="https://img.shields.io/badge/React-19-149ECA?logo=react&logoColor=white" alt="React" />
    <img src="https://img.shields.io/badge/TypeScript-5.7-3178C6?logo=typescript&logoColor=white" alt="TypeScript" />
    <img src="https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white" alt="Python" />
    <img src="https://img.shields.io/badge/Flask-Backend-111111?logo=flask&logoColor=white" alt="Flask" />
  </p>
</div>

---

## What is Brainy?

Brainy is a multi-provider AI assistant with a focus on making learning more interactive. Ask a question, unpack a difficult concept, work through a problem, or turn your study material into something you can actually revise.

Use it on the **web app** or through the **Telegram bot**. Under the hood, a task-aware routing layer selects from the providers and tools configured for the request — so a quick everyday question does not need to take the same path as a demanding reasoning task.

> **The idea:** AI should help you understand the answer, not just hand one to you.

## Why use Brainy?

| Benefit | Why it matters |
|:--|:--|
| **Learn, don't just look up** | Ask follow-up questions, request simpler explanations, and explore a concept from another angle. |
| **A more flexible AI stack** | The routing layer can use different configured providers for different kinds of work instead of tying every request to one model. |
| **Everyday tasks stay lightweight** | Normal Use mode is designed for quick questions, rewriting, translation, and other routine requests without loading the full specialist prompt. |
| **Turn documents into study material** | PDF Study Studio can extract and organize document content for notes, quizzes, and flashcard workflows. |
| **Practice active recall** | Use generated questions and flashcards to check what you remember, not only what you have read. |
| **Use it where you already chat** | Switch between a dedicated web workspace and the Telegram bot. |
| **Keep your study workspace organized** | Conversation history and workspace features help keep ongoing chats easy to revisit. |
| **Use the right tool for the task** | Supported arithmetic can use the local maths engine, while research-oriented tasks can use the configured search integration. |

*Provider access, model availability, usage limits, and some features depend on deployment configuration and the credentials supplied by the operator. Brainy does not promise unlimited or universally free third-party AI usage.*

## What you can do

### Study and understand
- Ask questions in natural language and continue with contextual follow-ups.
- Request step-by-step explanations and examples.
- Compare concepts, clarify terminology, and explore alternative explanations.
- Work through supported maths questions with the local maths engine where appropriate.

### Work with PDFs
- Upload study documents through PDF Study Studio.
- Extract and organize document text.
- Create revision notes, quizzes, and flashcards from available document content.
- Use local OCR support for scanned pages when the required OCR dependencies are installed.

### Get everyday help
- Rewrite messages, fix grammar, and translate text.
- Summarize notes and organize information.
- Brainstorm ideas and plan tasks.
- Get help with small coding questions and explanations.

### Research with context
- Use the configured search integration for research-oriented requests.
- Review source links when search results are returned.
- Keep in mind that search coverage and source quality vary; verify important information independently.

## Try asking Brainy

A few useful ways to get started:

- “Explain this concept like I am seeing it for the first time, then give me an example.”
- “Break this problem into steps and explain why each step works.”
- “Turn these notes into a concise revision sheet and a short practice quiz.”
- “Compare these two ideas in a table, including when each is useful.”
- “Translate this message naturally, but keep the tone polite.”
- “Help me plan the tasks I need to finish this week.”

The best results usually come from treating Brainy like a conversation: ask, review, follow up, and refine.

## How the AI routing works

Brainy classifies the request and its expected complexity, then uses the configured route that best fits the task. The exact model depends on the routing policy, available provider credentials, and provider availability.

| Route or integration | Intended role |
|:--|:--|
| **Normal Use** | Lightweight prompt path for routine questions, short writing tasks, translation, and everyday conversations. |
| **Local maths engine** | Deterministic handling for supported arithmetic and mathematical expressions. |
| **Groq** | Fast inference route for suitable everyday and quick-response tasks. |
| **Google Gemini** | Configured advanced, reasoning, and multimodal routes. |
| **SambaNova / Cerebras** | Additional inference candidates where enabled by the routing policy. |
| **OpenRouter** | Additional model access through the configured registry. |
| **Tavily** | Primary configured web-search integration. |
| **DuckDuckGo Instant Answer** | Limited fallback source when the primary search path is unavailable or does not provide useful results. |

The repository also contains direct provider integrations in the Telegram bot code. Those paths are separate from the central router and depend on their own configuration.

### Prompt architecture

Prompts live in `prompts/`. The application selects the appropriate prompt path for the task instead of treating every request as a specialist workflow.

- `prompts/normal_use.txt` — compact everyday interaction instructions.
- `prompts/system_prompt.txt` — the main Brainy system prompt.
- Other prompt files — task-specific instructions for supported workflows.

Normal Use is intended to reduce unnecessary prompt overhead; actual token usage and savings depend on the assembled request and provider-reported usage.

## Architecture

~~~mermaid
flowchart TD
    WEB["Brainy Web App"] --> API["Backend API"]
    TG["Telegram Bot"] --> API
    API --> AUTH["Authentication & validation"]
    AUTH --> ROUTER["Task-aware routing"]
    ROUTER --> LOCAL["Local maths / local tools"]
    ROUTER --> NORMAL["Normal Use prompt + fast route"]
    ROUTER --> ADVANCED["Advanced / specialist prompt routes"]
    ROUTER --> SEARCH["Search integrations"]
    LOCAL --> OUT["Response handling"]
    NORMAL --> OUT
    ADVANCED --> OUT
    SEARCH --> OUT
    API <--> DB[("Supabase / PostgreSQL")]
    PDF["PDF Study Studio"] --> EXTRACT["Local extraction & chunking"]
    EXTRACT --> OCR["Optional local OCR"]
    EXTRACT --> DOC["Document study workflows"]
    OCR --> DOC
    DOC --> API
    OUT --> WEB
    OUT --> TG
~~~

## Tech stack

| Layer | Technologies |
|:--|:--|
| **Frontend** | Next.js, React, TypeScript, Tailwind CSS |
| **Backend** | Python, Flask, Gunicorn |
| **AI orchestration** | Task classification, provider registry, routing policy, prompt selection, and fallback handling |
| **Database** | Supabase / PostgreSQL |
| **Document processing** | PyMuPDF, text extraction, chunking, optional Tesseract OCR |
| **Maths** | SymPy and a restricted local expression engine |
| **Search** | Tavily, DuckDuckGo Instant Answer |
| **Messaging** | Telegram Bot API |
| **Frontend hosting config** | Cloudflare Workers static assets |

## Run locally

### 1. Clone the repository

~~~bash
git clone https://github.com/shreyanshio/BrainyAi.git
cd BrainyAi
~~~

### 2. Install dependencies

~~~bash
npm install
python -m venv .venv
~~~

Activate the virtual environment, then install the Python dependencies:

~~~bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
~~~

### 3. Configure environment variables

Copy `.env.example` to `.env` and fill in only the credentials for the services you intend to use.

~~~bash
# Windows PowerShell
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
~~~

At minimum, configure the backend security values and the services required for the features you want to run. The frontend uses `NEXT_PUBLIC_API_URL` to locate the backend; for a local backend this is normally `http://localhost:5000`.

**Never commit your real `.env` file, API keys, service-role keys, or tokens.**

### 4. Start the backend

In one terminal, with the Python virtual environment activated:

~~~bash
python app.py
~~~

The Flask backend uses port `5000` by default.

### 5. Start the frontend

In another terminal:

~~~bash
npm run dev
~~~

Open [http://localhost:3000](http://localhost:3000).

### Optional services

- Start the Telegram bot separately with `python study_bot.py` after configuring its token and required provider credentials.
- Scanned-PDF OCR requires the Python OCR dependencies and a Tesseract executable available to the backend.
- AI providers, search, and database-backed features require the corresponding server-side configuration.

## Project structure

| Path | Purpose |
|:--|:--|
| `app/` | Next.js application routes and pages |
| `components/` | Reusable frontend components |
| `lib/` | Frontend utilities and API integration |
| `types/` | Shared TypeScript types |
| `ai_routing/` | Task classification, model registry, routing policy, and provider adapters |
| `pdf_studio/` | PDF extraction, chunking, OCR, and study workflows |
| `prompts/` | Main, everyday, and task-specific prompt resources |
| `logos/` | Approved brand assets and usage guide |
| `public/` | Static frontend assets |
| `app.py` | Flask backend API |
| `study_bot.py` | Telegram bot entry point |
| `security.py` | Backend authentication and security controls |

## Security notes

Brainy includes application-level authentication, request validation, rate-limiting, and security controls. These are not a guarantee that any deployment is breach-proof or independently certified.

For a safer deployment:

- Keep provider keys and database service-role credentials on the backend.
- Use strong, unique production secrets.
- Restrict allowed frontend origins.
- Configure Supabase policies for the actual tables and operations.
- Keep dependencies and deployment services updated.
- Never commit personal data, uploaded documents, or real environment files.

## Contributing

Issues, thoughtful feature suggestions, and pull requests are welcome.

1. Open an issue describing the problem or proposed change.
2. Keep changes focused and explain why they are useful.
3. Run the relevant checks before opening a pull request.
4. Never include API keys, private data, or production credentials.

<div align="center">

  <a href="https://github.com/shreyanshio/BrainyAi/issues/new"><img src="https://img.shields.io/badge/SUGGEST_A_FEATURE-6C63FF?style=for-the-badge&logo=github&logoColor=white" alt="Suggest a feature" /></a>
  <a href="https://github.com/shreyanshio/BrainyAi/issues/new"><img src="https://img.shields.io/badge/REPORT_AN_ISSUE-EA4335?style=for-the-badge&logo=github&logoColor=white" alt="Report an issue" /></a>
  <a href="https://github.com/shreyanshio/BrainyAi"><img src="https://img.shields.io/badge/EXPLORE_THE_CODE-24292F?style=for-the-badge&logo=github&logoColor=white" alt="Explore the code" /></a>

  <br />

  **Keep asking. Keep learning. Stay Brainy.**

</div>
