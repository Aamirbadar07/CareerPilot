# CareerPilot Agent Audit & AI Systems Evaluation

**Date:** 2026-11-02  
**Target:** Specialist AI Agents and LangGraph State Machine  
**Evaluator:** Agentic AI Systems Architect & LLM Engineer

---

## 1. Overview of Agents

CareerPilot decomposes career management into seven distinct specialist agents coordinated by a LangGraph orchestrator:

```
                          ┌────────────────────────┐
                          │ LangGraph Orchestrator │
                          └───────────┬────────────┘
                                      │
        ┌──────────────┬──────────────┼──────────────┬──────────────┐
        ▼              ▼              ▼              ▼              ▼
  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐
  │  Resume   │  │    Job    │  │ Fit Scorer│  │  Resume   │  │ LinkedIn  │
  │ Analyzer  │  │ Discovery │  │ (Weighted)│  │  Tailor   │  │ Optimizer │
  └───────────┘  └───────────┘  └───────────┘  └───────────┘  └───────────┘
                                      ▲              ▲
        ┌──────────────┐              │              │
        │ Career Coach │──────────────┘              │
        └──────────────┘                             │
        ┌──────────────┐                             │
        │ Credentials  │─────────────────────────────┘
        └──────────────┘ (Outside graph: user approval loop)
```

---

## 2. Detailed Agent Inspection

### Agent 1: Resume Analyzer (`app/agents/resume_analyzer/`)
- **Inputs:** Raw resume text (PDF/DOCX/TXT), source filename.
- **Outputs:** `MasterProfile` JSON schema, ATS score with component breakdown, weak bullet detection with suggested rewrites, missing keywords, and target roles.
- **Safety & Fact-Checking:**
  - `_no_unsupported_claims` validator enforces that every extracted skill traces to an existing evidence ID in experience, projects, or certifications.
  - ATS score arithmetic is strictly calculated in Python code (`sum(c.score for c in components)`), never trusting the LLM's self-reported sum.
  - Generates immutable version 1 of `MasterProfile`.

### Agent 2: Job Discovery (`app/agents/job_discovery/`)
- **Inputs:** Candidate target roles, seniority preferences, excluded companies, location preferences.
- **Sources:** Licensed feeds only (Remotive API, Greenhouse public job boards, JSearch RapidAPI). Web scraping is forbidden by design.
- **Filtering & Normalization:**
  - `prefilter` in deterministic Python drops jobs older than 45 days, excluded employers, exact duplicates, and senior titles for entry-level candidates.
  - Phase 2 normalization extracts structured must-haves and nice-to-haves.
  - **No-Invention Guard:** Discards any job whose URL was not fetched from the live source. Copies company name, location, and posting date directly from the verified source record. Validates salary figures against the raw text before accepting.

### Agent 3: Job Fit Scorer (`app/agents/fit_scorer/`)
- **Inputs:** Master profile (PII redacted) and job record.
- **Architecture:** Scores jobs across six weighted dimensions:
  1. Must-have skill coverage (35)
  2. Nice-to-have skill coverage (10)
  3. Experience depth vs requirement (20)
  4. Domain and project relevance (20)
  5. Seniority alignment (10)
  6. Location / remote / type fit (5)
- **Scoring Bands:**
  - `Strong`: 75–100
  - `Competitive`: 55–74
  - `Stretch`: 35–54
  - `Poor`: 0–34
- **Calibrated Capping Logic (Audit Improvement):**
  - *Single missing must-have:* Capped at 60 (`MUST_HAVE_CAP`), placing the candidate into "Competitive" if other dimensions are strong.
  - *Multiple (2+) missing must-haves:* Capped at 54 (`MULTI_MUST_HAVE_CAP`), strictly holding the candidate in "Stretch" (or "Poor" if total score < 35). This fixes the previously documented 2/6 fit-band evaluation failure where candidates missing multiple core requirements were labeled "Competitive".
  - Prohibits hiring probability language (e.g. "X% chance of an offer") via regex guard `_PROBABILITY`.

### Agent 4: Resume Tailor (`app/agents/resume_tailor/`)
- **Inputs:** Master profile, target job, fit report, experience tenure.
- **Dual-Call Adversarial Architecture:**
  1. *Writer Call:* Reorders bullets and emphasizes verified skills aligning with the target job.
  2. *Deterministic Guard (`guard.py`):* Rejects unevidenced numbers, new tools in skill lists, and softening phrases ("familiar with", "exposure to").
  3. *Adversarial Validator Call:* Evaluates whether rewritten bullets inflate titles, overstate team leadership, or claim unevidenced accomplishments.
  4. *Fallback Mechanism:* If validation fails after 2 attempts, returns the original untailored master profile.

### Agent 5: LinkedIn Optimizer (`app/agents/linkedin_optimizer/`)
- **Inputs:** Master profile, candidate's pasted LinkedIn profile text.
- **Constraints Enforced:**
  - Headlines constrained to < 220 characters.
  - Banned buzzwords filtered out (`aspiring`, `passionate`).
  - Exactly top 3 skills flagged as pinned.
  - No auto-posting: strictly outputs copy-paste text blocks.

### Agent 6: Credentials Agent (`app/agents/credentials/`)
- **Inputs:** Certificate PDF/image text, credential URL, or text statement.
- **Deterministic Truth Enforcement:**
  - Credential IDs and URLs must match substring evidence in the raw upload.
  - `verified` flag is set to `True` only if an actual credential ID or verifiable URL exists.
  - Generates LinkedIn "add certification" prefilled deep link.
  - Confirmation triggers Profile Version $N+1$, purging stale tailored resumes and coaching roadmaps.

### Agent 7: Career Coach (`app/agents/career_coach/`)
- **Inputs:** Master profile and all current fit reports.
- **Roadmap Synthesis:**
  - Groups missing skills across all target jobs into frequent blockers.
  - Delivers exactly 5 ranked actions (ranks 1 to 5).
  - Limits large efforts (> 40 hours) to at most 1 item.
  - Identifies "score ceiling" and jobs unlocked by completing each action.

### LangGraph Orchestrator (`app/agents/orchestrator/`)
- **Topology:** Centralized router with conditional cyclic transitions back to router node.
- **Routing Rules:**
  - Evaluates available inputs deterministically before invoking nodes.
  - An agent whose inputs can never arrive is marked skipped without blocking the pipeline.
  - Node errors retry once; second failure degrades the branch while allowing remaining independent agents to proceed.
- **Concurrency & Events:**
  - Streams real-time progress events via Server-Sent Events (`/api/runs/{id}/stream`).
  - Emits `{agent, status: started|succeeded|failed, detail}` at each transition.

