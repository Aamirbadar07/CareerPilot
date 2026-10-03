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
| Resume text extraction (PDF, DOCX, TXT; in memory, 5 MB cap) | `backend/app/core/resume_text.py` | Phase 2 |
| Resume Analyzer agent | `backend/app/agents/resume_analyzer/` | Phase 2 |
| Profile API: upload, read, delete-my-data | `backend/app/api/profiles.py` | Phase 2 |
| Per-IP rate limit, PII-redacting log filter | `backend/app/core/rate_limit.py`, `logging.py` | Phase 2 |
| Sample candidate (demo data and test fixtures) | `backend/app/sample/` | Phase 2 |
| `artifacts` table: every agent output, keyed by (profile, kind, ref) | `backend/app/db/models.py` | Phase 2 |

## How an agent call works

1. The agent builds a JSON input and calls `LLM.complete(system_prompt, inputs, Schema)`.
2. The response is repaired (fences, stray prose, trailing commas) and validated against the
   agent's Pydantic schema. Semantic rules, such as "every skill cites evidence that exists",
   are validators on that schema.
3. A failure is sent back to the model once with the validation error. A second failure raises
   `LLMError`, which the API turns into a 502. Error text names positions, never content.
4. A valid result is cached under `sha256(model, system, input)`.

Code, not the model, owns ids, versions, timestamps, provenance and arithmetic.

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
