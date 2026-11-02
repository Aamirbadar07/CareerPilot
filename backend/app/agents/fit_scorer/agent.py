import re
from concurrent.futures import ThreadPoolExecutor

from app.agents.fit_scorer.prompt import SYSTEM_PROMPT
from app.agents.fit_scorer.schema import (
    MULTI_MUST_HAVE_CAP,
    MUST_HAVE_CAP,
    WEIGHTS,
    FitReport,
    band_for,
)
from app.agents.job_discovery.schema import Job
from app.agents.resume_analyzer.schema import profile_ids
from app.core.config import settings
from app.core.llm import LLM, LLMError
from app.schemas.profile import MasterProfile

MAX_CONCURRENT = 10  # the orchestrator's limit for this agent
FREE_TIER_CONCURRENT = 4  # Gemini's free tier allows about five requests a minute per model
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


def project_profile_for_fit(profile: MasterProfile) -> dict:
    """Compact candidate projection: strips contact details, DB metadata, and unused target_roles,
    cutting token context by ~55% while preserving all bullet ids, titles, dates, and evidence ids."""
    return {
        "identity": {
            "full_name": profile.identity.full_name,
            "title_line": profile.identity.title_line,
            "location": profile.identity.location,
        },
        "skills": [
            {"name": s.name, "category": s.category, "evidence": s.evidence}
            for s in profile.skills
        ],
        "experience": [
            {
                "id": e.id,
                "company": e.company,
                "role": e.role,
                "location": e.location,
                "remote": e.remote,
                "start": e.start,
                "end": e.end,
                "current": e.current,
                "bullets": [{"id": b.id, "text": b.text} for b in e.bullets],
            }
            for e in profile.experience
        ],
        "projects": [
            {
                "id": pr.id,
                "name": pr.name,
                "one_liner": pr.one_liner,
                "bullets": [{"id": b.id, "text": b.text} for b in pr.bullets],
            }
            for pr in profile.projects
        ],
        "education": [
            {"degree": ed.degree, "field": ed.field, "institution": ed.institution, "end": ed.end}
            for ed in profile.education
        ],
        "preferences": {
            "remote_only": profile.preferences.remote_only,
            "locations": profile.preferences.locations,
        },
    }


def _job_for_llm(job: Job) -> dict:
    return job.model_dump(exclude={"mirrors"}) | {"description": job.description[:2000]}


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
        {"master_profile": project_profile_for_fit(profile), "job": _job_for_llm(job)},
        FitReport,
        profile_id=profile.profile_id,
        check=check,
    )
    # Arithmetic, the must-have cap and the band are applied in code, not trusted.
    report.score = sum(d.score for d in report.dimensions)
    must_haves = {_normalise(s) for s in job.must_have}
    missing_must_haves = [
        m for m in report.missing if m.type == "blocker" or _normalise(m.skill) in must_haves
    ]
    effective_cap = MULTI_MUST_HAVE_CAP if len(missing_must_haves) >= 2 else MUST_HAVE_CAP
    report.capped = bool(missing_must_haves) and report.score > effective_cap
    if report.capped:
        report.score = effective_cap
    report.band = band_for(report.score)
    return report


def max_concurrent() -> int:
    """How many jobs to score at once. Ten against Gemini's free tier means every batch is
    throttled on arrival and each retry then sleeps through the server's backoff, which is
    slower than sending fewer. Anthropic has no such ceiling at this scale."""
    return FREE_TIER_CONCURRENT if settings.llm_provider == "google" else MAX_CONCURRENT


def score_jobs(llm: LLM, profile: MasterProfile, jobs: list[Job]) -> dict[str, FitReport | None]:
    """Score every job, a few at a time (see max_concurrent). A job that fails is returned
    as None; one bad posting never blocks the rest."""

    def one(job: Job) -> FitReport | None:
        try:
            return score_job(llm, profile, job)
        except LLMError:
            return None

    with ThreadPoolExecutor(max_workers=max_concurrent()) as pool:
        return dict(zip((j.id for j in jobs), pool.map(one, jobs), strict=True))
