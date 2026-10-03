# Evaluation

What has been measured, how, and what has not been measured yet. Numbers in this file come
from running `backend/eval/run_eval.py`; nothing here is estimated.

```bash
cd backend
uv run python -m eval.run_eval          # section 1a only: no API calls, free
uv run python -m eval.run_eval --live   # all sections: calls the model and costs money
```

## Status

| Section | What it measures | Result |
|---|---|---|
| 1a | Code guard catch rate on poisoned resumes | **Measured**, below |
| 1b | Validator model catch rate on poison the code guard cannot see | **Not run yet** (needs an API key) |
| 2 | Fit-band agreement with hand labels | **Not run yet** (needs an API key) |
| 3 | Latency and cost per call | **Not run yet** (needs an API key) |

Every fixture under `backend/app/sample/` is hand-authored to the agents' output contracts.
None is a recording of model output, so the unit tests prove the code around the model
(parsing, guards, storage, orchestration), not the quality of the model's answers. Sections
1b, 2 and 3 are what measure that.

## 1. Fabrication catch rate

`backend/eval/poisoned.json` holds 16 variants of the sample tailored resume. Each changes
one line.

- 6 **code-layer** cases add something code can prove is absent: a number, a skills-list
  entry, a bullet id, a softened claim.
- 8 **semantic** cases are written to pass the code guard: ownership words ("led a team"),
  scale words ("production", "enterprise"), a tool named inside a bullet, an inflated title,
  a project attributed to the employer, an upgraded technique, an unmeasured outcome.
- 2 **clean** cases contain no fabrication. They measure false alarms.

### 1a. Code guard (measured 2026-10-03)

| | Result |
|---|---|
| Code-layer poison caught | 6 of 6 |
| Semantic poison caught | 0 of 8 |
| Clean resumes wrongly flagged | 0 of 2 |

The 0 of 8 is the design, not a defect: it is the reason a second model call exists. It
also states the code guard's limit plainly. A tool name inside a bullet ("deployed it to
Kubernetes") is not caught by code, because the guard checks tool names only in the skills
list. Only the validator stands between that sentence and the user.

### 1b. Validator model

Not run yet. The script reports semantic poison caught out of 8 and clean resumes wrongly
failed out of 2. Fill in:

| | Result |
|---|---|
| Semantic poison caught | _ of 8 |
| Clean resumes wrongly failed | _ of 2 |

## 2. Fit-band agreement

`backend/eval/labels.json` holds hand-assigned bands for job-profile pairs. It ships with
six pairs for the sample profile, labelled by the author of the fixtures. The pack's
done-when for the fit scorer is "scores and bands that you agree with on 10 real jobs":
add your own profile and ten real postings to the labels file before quoting this number.

| | Result |
|---|---|
| Bands that match the hand label | _ of 6 |

What the unit tests already establish about scoring: the score is the sum of the
dimensions, a missing must-have caps it at 60, the band always follows from the score, a
skill without profile evidence cannot be counted, and a stated hire probability is rejected.

## 3. Latency and cost

Not run yet. The script prints the median latency per agent call and the token cost of the
evaluation at the listed price for `ANTHROPIC_MODEL`.

| | Result |
|---|---|
| Median latency per agent call | _ s |
| Cost of one evaluation run | $ _ |

A full pipeline run makes about 2 calls for discovery, 1 per job for fit, 1 for the coach,
1 for LinkedIn if text was pasted, at most 1 for routing, and 2 to 4 per tailored resume.
Identical inputs are served from the content-hash cache and cost nothing.

## Other checks that were run

| Check | Result | Date |
|---|---|---|
| Backend unit tests | 113 passed, 2 skipped (PDF tests, no Pango on the dev machine) | 2026-10-03 |
| Profile round-trip on PostgreSQL 16.2 (embedded, via `pgserver`) | Passed; `data` column is `jsonb` | 2026-10-03 |
| Job sources live: Remotive and two Greenhouse boards, sample queries, no LLM | 33 relevant postings fetched, 12 kept after the code prefilter | 2026-10-03 |
| Lighthouse, production build, mobile emulation: landing, dashboard, jobs | Performance 92, 91, 93. Accessibility 100, 100, 100 | 2026-10-03 |
| Frontend unit tests (resume diff) | 4 passed | 2026-10-03 |

## Not verified

- No agent has been run against the real model. No API key was available during the build.
- PDF rendering. WeasyPrint needs Pango, which is not on the Windows dev machine. The two
  PDF tests run in CI and in the Docker image; neither has been run yet.
- The Docker image has not been built and nothing is deployed.
- JSearch. Its adapter is written from the documented response shape and tested against a
  fixture, but has not been called with a real key.
- "20+ deduped real jobs": the live check kept 12 from keyless sources alone.
