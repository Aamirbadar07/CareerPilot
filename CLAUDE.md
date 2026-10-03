# CareerPilot
Autonomous multi-agent career platform. A user uploads a resume; the system
analyses it, finds matching jobs across job APIs, scores fit, tailors a resume
per job, improves the LinkedIn profile, absorbs new certifications, and coaches
on skill gaps.

## Stack
- Backend: Python 3.11, FastAPI, Pydantic v2, Anthropic SDK (claude-sonnet-4-6)
- Orchestration: LangGraph (state machine, one node per agent)
- DB: Supabase / Postgres via SQLAlchemy + Alembic
- Queue: in-process background tasks for MVP; Celery + Redis later
- PDF: Jinja2 HTML template rendered by WeasyPrint
- Frontend: Next.js 14 App Router, TypeScript, Tailwind, shadcn/ui, Motion
- Deploy: frontend on Vercel, backend on Render

## Repo layout

```
backend/app/agents/<name>/{agent.py,prompt.py,schema.py,test_<name>.py}
backend/app/core/        config, llm client, logging, rate limits
backend/app/db/          models, migrations, repositories
backend/app/api/         FastAPI routers
backend/app/templates/   resume HTML templates
frontend/                Next.js app
docs/                    architecture.md, evaluation.md, decisions/
```

## Non-negotiable rules
1. NO FABRICATION. No agent may invent a skill, tool, employer, date, metric or
   certification that is not in the master profile. Every tailored claim must
   trace to a profile field. A validator runs after tailoring and FAILS the
   request on any unsupported claim.
2. ONE SOURCE OF TRUTH. The master profile JSON is the only shared state.
   Agents receive it as input and return structured patches, never free prose.
3. STRUCTURED I/O. Every agent returns JSON matching its Pydantic schema.
   Parse failures retry once with the validation error, then fail loudly.
4. NO SCRAPING of LinkedIn, Naukri, Indeed or any site forbidding it. Use the
   licensed APIs listed in docs/architecture.md, plus user-pasted job text.
5. NEVER AUTO-APPLY and never auto-post to LinkedIn. The system prepares;
   the human submits.
6. PRIVACY. Resume files are deleted after parsing. Never log resume text,
   emails or phone numbers. PII is redacted from traces.
7. SECRETS in .env only, loaded via pydantic-settings. Never commit .env.
8. TESTS. Every agent ships with tests using recorded fixture responses.
   No network calls in tests.
9. COST. Cache by content hash. Rate-limit per IP. Cap upload size at 5 MB.
10. COMMITS small and conventional (feat:, fix:, test:, docs:).

## Working agreement
- Show a plan before writing code for any new phase; wait for approval.
- One phase per session. Do not start the next phase unprompted.
- Prompts in prompt.py are authored deliberately. Do not rewrite them without
  being asked.
- Update docs/architecture.md whenever a component is added.
