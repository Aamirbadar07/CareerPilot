# CareerPilot AI Evaluation & Calibration Report

**Date:** 2026-11-02  
**Target:** AI Quality Gates, Fabrication Prevention, and Fit-Band Calibration  
**Evaluator:** AI Evaluation Scientist & QA Automation Engineer

---

## 1. Executive Summary

A critical finding from previous project evaluations (`docs/evaluation.md`) was a **2/6 fit-band agreement** rate between the model and hand-labeled ground truth when running on lightweight models.

This report documents the root-cause diagnosis, the engineering remediation implemented in code and prompts, and the verification of fabrication prevention layers.

---

## 2. Investigation of the 2/6 Fit-Band Agreement Defect

### 2.1 The Baseline Result
In the initial baseline run against `backend/eval/labels.json` on `gemini-3.5-flash-lite`:

| Job Title | Ground Truth Hand Label | Baseline Model Band | Baseline Score | Agreement |
|---|---|---|---|---|
| Generative AI Developer (Entry Level) | **Strong** | Strong | 98 | Agree |
| Junior AI Engineer | **Competitive** | Strong | 90 | **Disagree** (+1 Band) |
| Associate LLM Application Developer | **Stretch** | Competitive | 60 | **Disagree** (+1 Band) |
| Python Backend Developer I | **Competitive** | Competitive | 60 | Agree |
| ML Engineer - GenAI (Graduate) | **Stretch** | Competitive | 60 | **Disagree** (+1 Band) |
| AI Solutions Engineer | **Poor** | Stretch | 52 | **Disagree** (+1 Band) |

**Baseline Agreement:** 2 of 6 (33.3%). Every single disagreement was the model scoring exactly one band higher than the hand label.

### 2.2 Root Cause Analysis
Two interacting mechanisms caused this systematic upward bias:
1. **Uncalibrated Model Dimensions:** Smaller models scored dimensions leniently (e.g. awarding 30/35 for must-haves when only 2 of 4 were evidenced, or full points for nice-to-haves and tenure when the profile fell short of requirements).
2. **The 60-Point Cap Trap:** `MUST_HAVE_CAP = 60` was applied uniformly whenever *any* must-have was missing. However, the score band table defines:
   - `Strong`: 75–100
   - `Competitive`: 55–74
   - `Stretch`: 35–54
   - `Poor`: 0–34
   Because 60 falls squarely inside the `Competitive` band (55 to 74), any candidate with a missing must-have whose other dimensions were scored generously was capped at 60 and stamped as "Competitive"—even if they were missing multiple core blocker technologies (e.g. Paperkite missing both LangChain agents and AWS; Quillstack missing PyTorch and fine-tuning)!

---

## 3. The Calibrated Solution

We implemented a two-tier defense:

### 3.1 Tiered Code Capping (`app/agents/fit_scorer/`)
In `schema.py` and `agent.py`:
- `MUST_HAVE_CAP = 60`: Applied when exactly 1 must-have is missing. A candidate missing only 1 skill (e.g. Tallyroot missing `pytest`) who is otherwise stellar can realistically tailor their resume and compete.
- `MULTI_MUST_HAVE_CAP = 54`: Applied when 2 or more must-haves or blocker skills are missing. By definition, a candidate missing multiple core technologies cannot be "Competitive"; they are held at 54, placing them into the `Stretch` band (35–54).

```python
must_haves = {_normalise(s) for s in job.must_have}
missing_must_haves = [
    m for m in report.missing if m.type == "blocker" or _normalise(m.skill) in must_haves
]
effective_cap = MULTI_MUST_HAVE_CAP if len(missing_must_haves) >= 2 else MUST_HAVE_CAP
report.capped = bool(missing_must_haves) and report.score > effective_cap
if report.capped:
    report.score = effective_cap
report.band = band_for(report.score)
```

### 3.2 Dimension Calibration Rules (`app/agents/fit_scorer/prompt.py`)
Added explicit dimension calibration instructions to the system prompt:
- **Must-have skills (35):** Award points strictly proportional to evidenced skills (e.g. 2 of 4 evidenced = max 17/35).
- **Nice-to-have skills (10):** 0 points if none are evidenced.
- **Experience depth (20):** Compare actual tenure directly against requirements (e.g. 5 months vs 2+ years = max 5/20).
- **Seniority alignment (10):** Score based on actual level match (entry-level candidate applying for senior/consulting role = max 3/10).

---

## 4. Fabrication Catch Rate Verification

Evaluated via `backend/eval/run_eval.py` across 16 test cases in `backend/eval/poisoned.json`:

| Layer | Cases Tested | Caught | Missed | False Alarms | Pass Rate |
|---|---|---|---|---|---|
| **Deterministic Code Guard** (`guard.py`) | 6 code-layer poison | 6 | 0 | 0 of 2 clean | **100%** |
| **Semantic Poison (Code Layer)** | 8 semantic poison | 0 | 8 | N/A | Expected (delegated to validator) |
| **Adversarial Validator Model** | 8 semantic poison | 8 | 0 | 0 of 2 clean | **100%** |

- **Deterministic Code Guard Results:**
  - `CAUGHT` [code] invented user count ("scaled to 50,000 users")
  - `CAUGHT` [code] inflated metric ("reduced latency by 45%")
  - `CAUGHT` [code] invented percentage ("achieved 98% accuracy")
  - `CAUGHT` [code] invented skill in the skills list ("Kubernetes")
  - `CAUGHT` [code] bullet with no source (unreferenced ID)
  - `CAUGHT` [code] softened claim ("familiar with PyTorch")
  - `passed` [clean] clean sample resume (0 false alarms)
  - `passed` [clean] clean job wording for real fact (0 false alarms)

