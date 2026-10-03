# Architecture

Kept current per CLAUDE.md: update this file whenever a component is added.

## Components

| Component | Where | Status |
|---|---|---|
| Config (pydantic-settings, `.env`) | `backend/app/core/config.py` | Phase 0 |
| Health endpoint `GET /health` | `backend/app/api/health.py` | Phase 0 |
| Master profile model | `backend/app/schemas/profile.py` | Phase 0 |
| CI (ruff + pytest on Python 3.11) | `.github/workflows/ci.yml` | Phase 0 |
| DB models: `profiles`, `profile_versions`, `llm_cache` | `backend/app/db/models.py` | Phase 1 |
| Migrations (Alembic) | `backend/app/db/migrations/` | Phase 1 |
| Repositories and LLM response cache | `backend/app/db/repositories.py` | Phase 1 |
| LLM client: JSON repair, one validation retry, content-hash cache | `backend/app/core/llm.py` | Phase 1 |

## Data model

- `profiles` holds one row per candidate with an `expires_at`. NULL means the sample profile.
- `profile_versions` holds an immutable master-profile JSON snapshot per `(profile_id, version)`.
  Every change is a new row, so any change can be reversed.
- `llm_cache` maps `sha256(model, system prompt, input)` to the validated response, tagged with
  the profile it was computed for so a purge removes derived data too.

SQLite is the zero-config default for local runs; set `DATABASE_URL` for Postgres (Supabase).

`backend/app/schemas/profile_schema.json` is the example instance from the build pack.
`profile.py` is the enforced contract; a test fails if the two drift apart.

## Licensed job sources (CLAUDE.md rule 4: no scraping)

| Source | Covers | Access |
|---|---|---|
| JSearch (RapidAPI) | Google for Jobs feed, incl. LinkedIn and Indeed postings | Free tier, API key |
| Adzuna | Broad aggregator, India and global | Free app id and key |
| Remotive, RemoteOK, We Work Remotely | Remote-first roles | Public JSON, no key |
| Greenhouse, Lever, Ashby boards | Direct company career pages | Public JSON per company |
| Paste-a-link or paste-JD | Anything else, incl. Naukri | User-supplied |
