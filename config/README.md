# BrainyAi — Configuration & Dependency Reference

All configuration and dependency files **must remain in the project root** to be detected automatically by their respective tools. They are listed and documented here for reference.

---

## Frontend (Next.js / Cloudflare Workers)

| File | Tool | Purpose |
|------|------|---------|
| [`package.json`](../package.json) | npm / Node.js | Declares frontend dependencies, scripts (`dev`, `build`, `deploy`), and project metadata |
| [`package-lock.json`](../package-lock.json) | npm | Lockfile for reproducible installs — do not edit manually |
| [`next.config.mjs`](../next.config.mjs) | Next.js | Configures static export, API rewrites to the Railway backend, and image domains |
| [`tsconfig.json`](../tsconfig.json) | TypeScript | TypeScript compiler options — path aliases (`@/`), strict mode, target |
| [`postcss.config.mjs`](../postcss.config.mjs) | PostCSS / Tailwind | Enables Tailwind CSS and autoprefixer in the build pipeline |
| [`wrangler.jsonc`](../wrangler.jsonc) | Cloudflare Wrangler | Cloudflare Workers deployment config — worker name, assets dir, compatibility date |

## Backend (Python Flask / Railway)

| File | Tool | Purpose |
|------|------|---------|
| [`requirements.txt`](../requirements.txt) | pip | Python package dependencies (Flask, Gunicorn, groq, supabase, etc.) |
| [`Procfile`](../Procfile) | Railway / Heroku | Declares the process type (`web`) and the Gunicorn startup command |

---

## Key Scripts

```bash
# Frontend
npm run dev          # Local development server (http://localhost:3000)
npm run build        # Static export to out/
npx wrangler deploy  # Deploy to Cloudflare Workers

# Backend
pip install -r requirements.txt  # Install Python dependencies
gunicorn app:app                  # Start Flask server locally
```

---

> **Note:** Moving any of these files out of the project root will break the build or deployment. They are intentionally at the top level.
