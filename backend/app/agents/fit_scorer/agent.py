import re
from concurrent.futures import ThreadPoolExecutor

from app.agents.fit_scorer.prompt import SYSTEM_PROMPT
from app.agents.fit_scorer.schema import MUST_HAVE_CAP, WEIGHTS, FitReport, band_for
from app.agents.job_discovery.schema import Job
from app.agents.resume_analyzer.schema import profile_ids
from app.core.llm import LLM, LLMError
from app.schemas.profile import MasterProfile

MAX_CONCURRENT = 10  # the orchestrator's limit for this agent
# "70% of the must-haves" is fine; "70% chance" and "odds of getting hired" are not
_PROBABILITY = re.compile(
    r"\d\s?%\s*(chance|probability|likelihood|odds)"
    r"|\b(chance|probability|likelihood|odds) of (being hired|getting|an offer|an interview)",
    re.IGNORECASE,
)


def profile_for_llm(profile: MasterProfile) -> dict:
    """The profile without contact details. No agent after the analyzer needs them, so they
    are not sent to the model."""
    data = profile.model_dump(exclude={"provenance"})
    for field in ("email", "phone"):
        data["identity"][field] = None
    return data


def _job_for_llm(job: Job) -> dict:
    return job.model_dump(exclude={"mirrors"}) | {"description": job.description[:3000]}


def _normalise(skill: str) -> str:
    return re.sub(r"[^a-z0-9+#]+", " ", skill.lower()).strip()


def score_job(llm: LLM, profile: MasterProfile, job: Job) -> FitReport:
    evidence_ids, _ = profile_ids(profile)

    def check(report: FitReport) -> None:
        if sorted(d.max for d in report.dimensions) != sorted(WEIGHTS):
            raise ValueError(f"dimensions must be the six weighted ones with max {WEIGHTS}")
        for i, d in enumerate(report.dimensions):
            if not 0 <= d.score <= d.max:
                raise ValueError(f"dimensions[{i}].score is outside 0..max")
        for i, m in enumerate(report.matched):
            if m.evidence not in evidence_ids:
                raise ValueError(
                    f"matched[{i}].evidence is not an id in the profile; a skill without "
                    "evidence must be listed under missing"
                )
        prose = [report.verdict, report.resume_angle, *(d.why for d in report.dimensions)]
        if any(_PROBABILITY.search(text) for text in prose):
            raise ValueError("states a probability of being hired; give the band and reasoning")

    report = llm.complete(
        SYSTEM_PROMPT,
        {"master_profile": profile_for_llm(profile), "job": _job_for_llm(job)},
        FitReport,
        profile_id=profile.profile_id,
        check=check,
    )
    # Arithmetic, the must-have cap and the band are applied in code, not trusted.
    report.score = sum(d.score for d in report.dimensions)
    must_haves = {_normalise(s) for s in job.must_have}
    missing_must_have = any(
        m.type == "blocker" or _normalise(m.skill) in must_haves for m in report.missing
    )
    report.capped = missing_must_have and report.score > MUST_HAVE_CAP
    if report.capped:
        report.score = MUST_HAVE_CAP
    report.band = band_for(report.score)
    return report


def score_jobs(llm: LLM, profile: MasterProfile, jobs: list[Job]) -> dict[str, FitReport | None]:
    """Score every job, at most MAX_CONCURRENT at a time. A job that fails is returned as
    None; one bad posting never blocks the rest."""

    def one(job: Job) -> FitReport | None:
        try:
            return score_job(llm, profile, job)
        except LLMError:
            return None

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as pool:
        return dict(zip((j.id for j in jobs), pool.map(one, jobs), strict=True))
