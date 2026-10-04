# CareerPilot

[![Live Demo](https://img.shields.io/badge/Live_Demo-career--pilot--lac.vercel.app-brightgreen?style=for-the-badge&logo=vercel)](https://career-pilot-lac.vercel.app)
[![API Status](https://img.shields.io/badge/Backend_API-Cloud_Run_Live-blue?style=for-the-badge&logo=googlecloud)](https://careerpilot-backend-473372801300.us-central1.run.app/health)

> 🚀 **Live Production Application:** [https://career-pilot-lac.vercel.app](https://career-pilot-lac.vercel.app)

A multi-agent career platform. You upload a resume. Seven agents turn it into a structured
profile, find matching jobs through licensed feeds, score each fit, tailor a one-page resume
to the job you pick, write LinkedIn text, absorb new certifications and plan what to do next.

Two rules shape everything:

- **Nothing is invented.** Every tailored line traces to a fact in your profile. Code
  rejects numbers, skills and ids that are not there, then a separate model call
  fact-checks the rest. If it fails twice, you get your original resume back.
- **Nothing is sent for you.** No scraping, no auto-applying, no posting to LinkedIn.

![Landing page](docs/landing-preview.jpg)

## Status

Deployed: the frontend on Vercel, the backend on Cloud Run, and the PDF renderer works
there (a tailored resume downloads as a one-page PDF). The agents are still mostly
unmeasured: **only the fact-checker and the fit scorer have run against a real model
(Gemini Flash-Lite), and nothing has run on Claude, the model the prompts were written
for.** [`docs/evaluation.md`](docs/evaluation.md) lists what was measured and what was not.

## How it works

```mermaid
flowchart LR
    U[Upload resume] --> R{router}
    R --> A[resume_analyzer] --> R
    R --> J[job_discovery] --> R
    R --> F[fit_scorer] --> R
    R --> T[resume_tailor] --> R
    R --> L[linkedin_optimizer] --> R
    R --> C[career_coach] --> R
    R --> E([done])
    K[credentials] -. user confirms .-> P[(master profile)]
    A -.-> P
    P -. read by every agent .-> R
```

| Agent | Reads | Produces |
|---|---|---|
| Resume analyzer | resume text | master profile, ATS score, weak-bullet fixes |
| Job discovery | target roles, preferences | deduplicated jobs from Remotive, Greenhouse, JSearch |
| Fit scorer | profile, one job | score from six weighted dimensions, band, matched and missing skills |
| Resume tailor | profile, job, fit report | one-page resume content, validated by a second call |
| LinkedIn optimizer | profile, pasted LinkedIn text | headlines, About, consistency check |
| Credentials | certificate, link or statement | a profile patch that the user confirms |
| Career coach | profile, all fit reports | five ranked actions |

The master profile is the only shared state. It is versioned: every change is a new row
with a change-log entry naming the agent and the user's approval.

**The loop.** A confirmed certificate creates a new profile version. Tailored resumes and
the coaching plan are dropped, fit scores and LinkedIn text go stale, and the next run of
each uses the new profile. One upload improves every later output without anyone
re-running anything by hand. That feedback path is what makes this an agent system rather
than a one-way pipeline.

More detail: [`docs/architecture.md`](docs/architecture.md).

## Run it locally

You need [uv](https://docs.astral.sh/uv/) and Node 22.18 or newer.

```bash
cd backend
uv sync
cp .env.example .env        # then set ANTHROPIC_API_KEY, or LLM_PROVIDER=google and GOOGLE_API_KEY
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. Without an API key the app still works in **demo mode**: a
fictional sample profile with jobs, fit reports, a tailored resume, LinkedIn text and a
coaching plan. Uploading your own resume needs the key.

| Variable | Needed for | Default |
|---|---|---|
| `LLM_PROVIDER` | which model family runs the agents: `anthropic` or `google` | `anthropic` |
| `ANTHROPIC_API_KEY` | every agent, when the provider is `anthropic` | none |
| `ANTHROPIC_MODEL` | model choice | `claude-sonnet-4-6` |
| `GOOGLE_API_KEY` | every agent, when the provider is `google` (a Gemini key from Google AI Studio) | none |
| `GOOGLE_MODEL` | model choice | `gemini-3.8-flash` |
| `DATABASE_URL` | Postgres (Supabase) | a local SQLite file |
| `RAPIDAPI_KEY` | JSearch job source | source skipped |
| `GREENHOUSE_BOARDS` | which company boards to read | `gitlab` |
| `FRONTEND_ORIGIN` | CORS | `http://localhost:3000` |
| `TRUSTED_PROXY_HOPS` | proxies in front of the app, so the per-IP rate limit reads a real address and not one a caller typed | `1` |
| `NEXT_PUBLIC_API_URL` (frontend) | where the API is | `http://localhost:8000` |

Local Postgres instead of SQLite: `docker compose up -d db`, then
`DATABASE_URL=postgresql://postgres:careerpilot@localhost:5433/careerpilot`.

PDF download needs WeasyPrint's native library, Pango. The Docker image has it. On Windows
without it the PDF route returns 501 and the HTML print view still works.

## Test and evaluate

```bash
cd backend && uv run pytest              # no network, no API key
cd backend && uv run python -m eval.run_eval          # code-guard catch rate, free
cd backend && uv run python -m eval.run_eval --live   # validator, fit agreement, cost
cd frontend && npm test && npm run lint && npm run typecheck
```

## Deploy

- **Backend on Cloud Run** (what the live API runs on): build `backend/Dockerfile` and
  deploy it, with `ANTHROPIC_API_KEY` (or `GOOGLE_API_KEY` and `LLM_PROVIDER=google`),
  `DATABASE_URL` and `FRONTEND_ORIGIN` set on the service. One proxy sits in front, so the
  default `TRUSTED_PROXY_HOPS=1` is right; add one for each extra load balancer or CDN.
- **Backend on Render:** `render.yaml` is a blueprint that builds the same image. Set the
  same variables in the dashboard.
- **Frontend on Vercel:** import the repo, set the root directory to `frontend` and
  `NEXT_PUBLIC_API_URL` to the backend URL.

## Decisions

- [0001 Licensed job APIs and pasted text, no scraping](docs/decisions/0001-licensed-apis-not-scraping.md)
- [0002 A fit band, never a hire probability](docs/decisions/0002-band-not-probability.md)
- [0003 Layout lives in a template, not in the model](docs/decisions/0003-layout-in-template.md)
- [0004 Demo mode: a sample profile plus self-deleting uploads](docs/decisions/0004-demo-mode.md)

Privacy: [`docs/privacy.md`](docs/privacy.md).
