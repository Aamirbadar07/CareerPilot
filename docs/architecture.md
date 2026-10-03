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
| Job sources: Remotive, Greenhouse boards, JSearch | `backend/app/agents/job_discovery/sources.py` | Phase 3 |
| Job Discovery agent: query plan, code prefilter, normalise, no-invention guard | `backend/app/agents/job_discovery/agent.py` | Phase 3 |
| Jobs API: discover, paste a description, list | `backend/app/api/jobs.py` | Phase 3 |
| Fit scorer agent: six weighted dimensions, cap and band in code, 10 jobs at a time | `backend/app/agents/fit_scorer/` | Phase 4 |
| Fit API: scores cached per (profile version, job) | `backend/app/api/jobs.py` | Phase 4 |

## How job discovery works

1. The model expands target roles into 8-15 queries (phase 1 of its prompt).
2. Code fetches every source. Feeds (Remotive, Greenhouse) are fetched whole, cached for six
   hours and filtered by title against the queries; JSearch is a search API with a quota, so
   it receives at most five queries per run and is skipped when `RAPIDAPI_KEY` is empty.
3. Code drops what needs no judgement: older than 45 days, excluded companies, exact
   duplicates, titles above an entry-level band. The newest 30 survivors go on.
4. The model merges fuzzy duplicates, drops spam and location mismatches, and extracts
   must-haves, stack, years and salary (phase 2).
5. Code rejects any job whose URL was not fetched, copies title, company, location and date
   from the source rather than the model, and blanks a salary whose digits are not in the
   posting.

A source that fails is listed under `dropped` and the run continues.

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

Wired so far: Remotive, Greenhouse, JSearch and pasted descriptions. Remotive's terms require
a link back to the Remotive URL and naming Remotive as the source, and ask for at most about
four fetches a day; the job card links to the source URL and shows the source name, and the
feed is cached for six hours.
