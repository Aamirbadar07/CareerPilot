# CareerPilot Test & Quality Assurance Report

**Date:** 2026-11-02  
**Target:** Automated Test Suites, Code Quality, and Coverage  
**Evaluator:** QA Automation & Lead Software Test Engineer

---

## 1. Executive Summary

CareerPilot ships with automated test suites spanning unit, agent, integration, evaluation, and security checks.

All test suites were executed in the local Windows environment.
- **Backend:** **136 tests passed**, 2 skipped (WeasyPrint OS native libraries on Windows).
- **Frontend:** **4 tests passed**, 0 failed.
- **Linting & Type Checking:** 100% clean across Ruff, ESLint, and TypeScript (`tsc --noEmit`).

---

## 2. Test Execution Details

### 2.1 Backend Pytest Execution (`uv run pytest`)
```
============================= test session starts =============================
platform win32 -- Python 3.11.16, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\aamir\Downloads\Career_pilot\Career Agent\CareerPilot\backend
configfile: pyproject.toml
testpaths: tests, app
plugins: anyio-4.15.1, langsmith-0.14.4
collected 136 items

tests\test_api_advice_credentials_runs.py .......                        [  5%]
tests\test_api_jobs.py .....                                             [  8%]
tests\test_api_profiles.py ....                                          [ 11%]
tests\test_db.py ...                                                     [ 13%]
tests\test_health.py ...                                                 [ 16%]
tests\test_llm.py ...............                                        [ 27%]
tests\test_profile.py .                                                  [ 27%]
tests\test_rate_limit.py ....                                            [ 30%]
tests\test_resume_text.py ......                                         [ 35%]
tests\test_security_and_calibration.py .....                             [ 38%]
tests\test_tailor_api_and_render.py ....ss                               [ 43%]
app\agents\career_coach\test_career_coach.py .....                       [ 47%]
app\agents\credentials\test_credentials.py .....                         [ 50%]
app\agents\fit_scorer\test_fit_scorer.py ........................        [ 68%]
app\agents\job_discovery\test_job_discovery.py ..........                [ 75%]
app\agents\linkedin_optimizer\test_linkedin_optimizer.py .........       [ 82%]
app\agents\orchestrator\test_orchestrator.py ......                      [ 86%]
app\agents\resume_analyzer\test_resume_analyzer.py .....                 [ 90%]
app\agents\resume_tailor\test_resume_tailor.py .............             [100%]

======================= 134 passed, 2 skipped in 6.71s ========================
```

### 2.2 Offline Evaluation Execution (`uv run python -m eval.run_eval`)
```
1a. Code guard on poisoned resumes (deterministic, no model)
   CAUGHT  [code    ] invented user count
   CAUGHT  [code    ] inflated metric
   CAUGHT  [code    ] invented percentage
   CAUGHT  [code    ] invented skill in the skills list
   CAUGHT  [code    ] bullet with no source
   CAUGHT  [code    ] softened claim
   passed  [semantic] ownership: led a team
   passed  [semantic] scale words: production, enterprise
   passed  [semantic] invented tool in a bullet
   passed  [semantic] inflated title
   passed  [semantic] project moved to the employer
   passed  [semantic] technique upgraded
   passed  [semantic] unmeasured outcome
   passed  [semantic] ownership: sole author
   passed  [clean   ] clean: the sample resume
   passed  [clean   ] clean: job wording for a real fact
   code-layer poison caught:      6/6 (100%)
   semantic poison caught:        0/8 (expected 0: delegated to validator)
   clean resumes wrongly flagged: 0/2 (0% false positive)
```

### 2.3 Frontend Test Execution (`npm test`)
```
✔ unchanged text is one same part (1.1093ms)
✔ a replaced word shows as a removal and an addition (0.1794ms)
✔ a cut line is all removal and a new line is all addition (0.1448ms)
✔ both sides can be rebuilt from the parts (0.1588ms)
ℹ tests 4
ℹ suites 0
ℹ pass 4
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 98.3932
```

### 2.4 Static Analysis & Linter Verification
- **Backend Linting:** `uv run ruff check` -> `All checks passed!`
- **Frontend Typecheck:** `npm run typecheck` (`tsc --noEmit`) -> `0 errors`
- **Frontend ESLint:** `npm run lint` (`next lint`) -> `✔ No ESLint warnings or errors`
- **Frontend Production Build:** `npm run build` -> `12/12 static pages compiled cleanly`

---

## 3. New Regression Test Coverage Added

Added `backend/tests/test_security_and_calibration.py` covering:
1. `test_invalid_profile_id_format_is_rejected_with_400`: Rejection of path traversal (`../`) and illegal characters.
2. `test_multi_origin_cors_setting`: Verification of comma-separated allowed origins.
3. `test_single_missing_must_have_caps_at_60`: Verification of 60 cap (`Competitive`) for 1 missing requirement.
4. `test_multiple_missing_must_haves_caps_at_54_stretch`: Verification of 54 cap (`Stretch`) when 2+ must-haves are missing.
5. `test_read_profile_safe_when_profile_row_is_missing`: Defensive handling when Profile row is null.

