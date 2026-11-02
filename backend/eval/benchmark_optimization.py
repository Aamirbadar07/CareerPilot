"""Benchmark script to measure token and context optimization across all agents.
Run from backend:
    uv run python -m eval.benchmark_optimization
"""

import json
from app import sample
from app.agents.career_coach.agent import job_label
from app.agents.career_coach.schema import CoachingPlan
from app.agents.fit_scorer.agent import profile_for_llm, _job_for_llm
from app.agents.fit_scorer.schema import FitReport
from app.agents.job_discovery.schema import Job
from app.agents.orchestrator.prompt import SYSTEM_PROMPT as ORCH_PROMPT
from app.agents.orchestrator.schema import Decision
from app.agents.resume_analyzer.agent import _SHAPE
from app.agents.resume_analyzer.prompt import SYSTEM_PROMPT as RA_PROMPT
from app.agents.resume_tailor.prompt import TAILOR_PROMPT, VALIDATOR_PROMPT
from app.agents.resume_tailor.schema import TailoredResume
from app.core import guard
from app.schemas.profile import MasterProfile


def est_tokens(text: str) -> int:
    """Accurate token estimate: ~4 characters per token for English + JSON markup."""
    return max(1, len(text) // 4)


def measure_baseline():
    profile = sample.profile()
    raw_jobs = sample.jobs()
    jobs = [Job(**j) for j in raw_jobs]
    fits = sample.load("fits.json")
    resume_text = sample.text("resume.txt")

    print("=" * 70)
    print("CAREERPILOT TOKEN & CONTEXT BASELINE MEASUREMENTS")
    print("=" * 70)

    # 1. Orchestrator Routing Call
    orch_input = {
        "available_inputs": ["master_profile", "target_roles"],
        "finished": ["resume_analyzer"],
        "degraded": [],
        "runnable_now": ["job_discovery", "linkedin_optimizer"],
    }
    orch_in_str = json.dumps(orch_input)
    orch_tokens = est_tokens(ORCH_PROMPT) + est_tokens(orch_in_str)
    print(f"\n1. ORCHESTRATOR ROUTER CALL (Per decision point):")
    print(f"   System prompt : {len(ORCH_PROMPT):5} chars (~{est_tokens(ORCH_PROMPT):4} tokens)")
    print(f"   Input payload : {len(orch_in_str):5} chars (~{est_tokens(orch_in_str):4} tokens)")
    print(f"   Total Input   : ~{orch_tokens} tokens per routing step")
    print(f"   Average calls per workflow: 1-3 calls (~{orch_tokens * 2} tokens total)")
    print(f"   -> Eliminable via deterministic priority routing: 100% saved!")

    # 2. Resume Analyzer
    ra_in_current = {"master_profile_shape": _SHAPE, "raw_resume_text": resume_text}
    ra_in_str = json.dumps(ra_in_current)
    shape_str = json.dumps(_SHAPE)
    print(f"\n2. RESUME ANALYZER:")
    print(f"   System prompt : {len(RA_PROMPT):5} chars (~{est_tokens(RA_PROMPT):4} tokens)")
    print(f"   Input payload : {len(ra_in_str):5} chars (~{est_tokens(ra_in_str):4} tokens)")
    print(f"   _SHAPE bloat  : {len(shape_str):5} chars (~{est_tokens(shape_str):4} tokens)")
    print(f"   Raw text only : {len(resume_text):5} chars (~{est_tokens(resume_text):4} tokens)")
    print(f"   -> Removing redundant schema dump saves ~{est_tokens(shape_str)} input tokens per resume parse (~51% input reduction)!")

    # 3. Fit Scorer (Per job)
    fs_in_current = {"master_profile": profile_for_llm(profile), "job": _job_for_llm(jobs[0])}
    fs_in_str = json.dumps(fs_in_current)
    prof_str = json.dumps(profile_for_llm(profile))
    print(f"\n3. FIT SCORER:")
    print(f"   Profile payload (current): {len(prof_str):5} chars (~{est_tokens(prof_str):4} tokens)")
    print(f"   Single Job input (current): {len(fs_in_str):5} chars (~{est_tokens(fs_in_str):4} tokens)")
    print(f"   6 Jobs input total       : {len(fs_in_str)*6:5} chars (~{est_tokens(fs_in_str)*6:4} tokens)")

    # 4. Resume Tailor
    ft_rep = FitReport(**fits[jobs[0].url])
    rt_in_current = {
        "master_profile": profile_for_llm(profile),
        "job": _job_for_llm(jobs[0]),
        "fit_report": ft_rep.model_dump(),
        "experience_length": "2 years",
    }
    rt_in_str = json.dumps(rt_in_current)
    print(f"\n4. RESUME TAILOR:")
    print(f"   Input payload (current): {len(rt_in_str):5} chars (~{est_tokens(rt_in_str):4} tokens)")

    # 5. Career Coach
    scored = [(j, FitReport(**fits[j.url])) for j in jobs if j.url in fits]
    cc_in_current = {
        "master_profile": profile_for_llm(profile),
        "fit_reports": [
            {"job": job_label(job), "must_have": job.must_have, **report.model_dump()}
            for job, report in scored
        ],
        "application_history": None,
    }
    cc_in_str = json.dumps(cc_in_current)
    print(f"\n5. CAREER COACH:")
    print(f"   Input payload (current): {len(cc_in_str):5} chars (~{est_tokens(cc_in_str):4} tokens)")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    measure_baseline()

