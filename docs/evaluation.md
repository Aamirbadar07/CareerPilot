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
| 1b | Validator model catch rate on poison the code guard cannot see | **Measured** on `gemini-3.5-flash-lite`, below |
| 2 | Fit-band agreement with hand labels | **Measured** on `gemini-3.5-flash-lite`, below: 2 of 6 |
| 3 | Latency and cost per call | Latency **measured**; cost not computed (free tier) |

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

Measured 2026-10-03 on `gemini-3.5-flash-lite` (Google free tier), one run.

| | Result |
|---|---|
| Semantic poison caught | 8 of 8 |
| Clean resumes wrongly failed | 0 of 2 |

Eight cases and one run is a small sample: it shows the validator works on these kinds of
poison, not what its miss rate is. Add cases to `poisoned.json` before quoting a rate.

## 2. Fit-band agreement

`backend/eval/labels.json` holds hand-assigned bands for job-profile pairs. It ships with
six pairs for the sample profile, labelled by the author of the fixtures. The pack's
done-when for the fit scorer is "scores and bands that you agree with on 10 real jobs":
add your own profile and ten real postings to the labels file before quoting this number.

Measured 2026-10-03 on `gemini-3.5-flash-lite`, one run.

| Job | Hand label | Model band | Model score |
|---|---|---|---|
| Generative AI Developer (Entry Level) | Strong | Strong | 98 |
| Junior AI Engineer | Competitive | Strong | 90 |
| Associate LLM Application Developer | Stretch | Competitive | 60 |
| Python Backend Developer I | Competitive | Competitive | 60 |
| ML Engineer - GenAI (Graduate) | Stretch | Competitive | 60 |
| AI Solutions Engineer | Poor | Stretch | 52 |

**Agreement: 2 of 6.** Every disagreement is the model scoring one band higher than the
hand label. Two things explain it:

- The model is generous on the dimensions. It gave 98 where the hand score was 89.
- Three jobs sit at exactly 60. That is the must-have cap, and 60 falls inside the
  Competitive band (55 to 74). So any job with a missing must-have and generous dimension
  scores is reported as Competitive, even with two must-haves missing. The prompt's cap and
  its band table interact this way by design; whether a capped job should be able to read
  "Competitive" is an open question for the prompt's author.

This is the smallest and cheapest Gemini model, and the prompts were written for Claude.
Re-run on the intended model before drawing conclusions about the scorer.

What the unit tests already establish about scoring: the score is the sum of the
dimensions, a missing must-have caps it at 60, the band always follows from the score, a
skill without profile evidence cannot be counted, and a stated hire probability is rejected.

## 3. Latency and cost

Measured 2026-10-03 on `gemini-3.5-flash-lite`: 16 calls, 39,181 input tokens and 5,135
output tokens.

| | Result |
|---|---|
| Median latency per agent call | 1.9 s |
| Validation retries needed | 0 of 16 calls |
| Cost of one evaluation run | not computed: run on the free tier, and no Gemini price is listed in the script |

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

- Only the validator and the fit scorer have run against a real model, and only on
  `gemini-3.5-flash-lite`. The analyzer, job discovery, tailor, LinkedIn, credentials and
  coach agents have not. Nothing has run on Claude, the model the prompts were written for.
- The Gemini free tier is tight: `gemini-3.8-flash` ran out of daily quota during the first
  attempt, so the default Gemini model has not completed an evaluation.
- PDF rendering. WeasyPrint needs Pango, which is not on the Windows dev machine. The two
  PDF tests run in CI and in the Docker image; neither has been run yet.
- The Docker image has not been built and nothing is deployed.
- JSearch. Its adapter is written from the documented response shape and tested against a
  fixture, but has not been called with a real key.
- "20+ deduped real jobs": the live check kept 12 from keyless sources alone.
