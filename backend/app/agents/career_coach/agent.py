from app.agents.career_coach.prompt import SYSTEM_PROMPT
from app.agents.career_coach.schema import CoachingPlan
from app.agents.fit_scorer.agent import profile_for_llm
from app.agents.fit_scorer.schema import FitReport
from app.agents.job_discovery.schema import Job
from app.core.guard import norm
from app.core.llm import LLM
from app.schemas.profile import MasterProfile

LARGE_HOURS = 40  # an action above this is "large"; the prompt allows one at a time


def job_label(job: Job) -> str:
    return f"{job.title} ({job.company})"


def _same_skill(a: str, b: str) -> bool:
    """ "AWS" and "AWS (hands-on)" are one gap: one name's words contain the other's."""
    x, y = set(norm(a).split()), set(norm(b).split())
    return bool(x and y) and (x <= y or y <= x)


def coach(llm: LLM, profile: MasterProfile, scored: list[tuple[Job, FitReport]]) -> CoachingPlan:
    """One plan from all fit reports at once: the patterns no single job shows."""
    labels = {job_label(job) for job, _ in scored}

    def check(plan: CoachingPlan) -> None:
        problems = []
        if [a.rank for a in plan.plan] != [1, 2, 3, 4, 5]:
            problems.append("plan must hold exactly 5 actions ranked 1 to 5 in order")
        if sum(a.effort_hours > LARGE_HOURS for a in plan.plan) > 1:
            problems.append(f"more than one action is large (over {LARGE_HOURS} hours)")
        named = [("score_ceiling.jobs_moved", plan.score_ceiling.jobs_moved)]
        named += [(f"plan[{i}].jobs_unlocked", a.jobs_unlocked) for i, a in enumerate(plan.plan)]
        for where, jobs in named:
            if set(jobs) - labels:
                problems.append(f"{where} names a job that is not in fit_reports; use its label")
        if problems:
            raise ValueError("; ".join(problems))

    plan = llm.complete(
        SYSTEM_PROMPT,
        {
            "master_profile": profile_for_llm(profile),
            "fit_reports": [
                {"job": job_label(job), "must_have": job.must_have, **report.model_dump()}
                for job, report in scored
            ],
            "application_history": None,
        },
        CoachingPlan,
        profile_id=profile.profile_id,
        check=check,
    )
    # Counts come from the data, not the model. A "pattern" no report contains is dropped.
    total = len(scored)
    for gap in plan.pattern_gaps:
        gap.blocks_n_jobs = sum(
            any(_same_skill(gap.skill, m.skill) for m in report.missing) for _, report in scored
        )
        gap.pct_of_targets = round(100 * gap.blocks_n_jobs / total) if total else 0
    plan.pattern_gaps = sorted(
        (g for g in plan.pattern_gaps if g.blocks_n_jobs), key=lambda g: -g.blocks_n_jobs
    )
    return plan
