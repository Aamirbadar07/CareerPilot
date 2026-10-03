"""One function per pipeline step: run the agent, store what it produced. API routes and the
orchestrator's graph nodes both call these, so a step behaves the same either way."""

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.agents.career_coach.agent import coach, job_label
from app.agents.career_coach.schema import CoachingPlan
from app.agents.fit_scorer.agent import score_job, score_jobs
from app.agents.fit_scorer.schema import FitReport
from app.agents.job_discovery.agent import discover_jobs
from app.agents.job_discovery.schema import Job, JobDiscoveryResult
from app.agents.linkedin_optimizer.agent import optimize_linkedin
from app.agents.linkedin_optimizer.schema import LinkedInOptimizationResult
from app.agents.resume_analyzer.agent import analyze_resume
from app.agents.resume_analyzer.schema import ResumeAnalysisResult
from app.agents.resume_tailor.agent import tailor_resume
from app.agents.resume_tailor.schema import TailorResult
from app.core import render
from app.core.config import settings
from app.core.llm import LLM
from app.db import repositories as repo
from app.schemas.profile import MasterProfile

# Derived from the profile as a whole, so a profile change makes them wrong.
STALE_ON_PROFILE_CHANGE = ("tailored_resume", "coaching_plan")


def _put(db: Session, profile: MasterProfile, kind: str, data: dict, ref: str = "") -> None:
    repo.put_artifact(db, profile.profile_id, kind, data, profile.version, ref)


def current(db: Session, profile: MasterProfile, kind: str, ref: str = "") -> dict | None:
    """An artifact computed against the current profile version, else None. One from an older
    version is stale: the profile changed, so the result may have too."""
    artifact = repo.get_artifact(db, profile.profile_id, kind, ref)
    return artifact.data if artifact and artifact.profile_version == profile.version else None


def ingest_resume(db: Session, llm: LLM, text: str, source_file: str) -> ResumeAnalysisResult:
    result = analyze_resume(llm, text, source_file)
    profile = result.master_profile
    repo.save_profile(db, profile, ttl=timedelta(hours=settings.profile_ttl_hours))
    _put(db, profile, "resume_analysis", result.model_dump(exclude={"master_profile"}))
    return result


def save_new_version(db: Session, profile: MasterProfile) -> None:
    """Store an already-bumped profile and drop what the change made stale. Jobs carry over.
    Fit reports and LinkedIn copy are keyed by profile version, so they simply stop being
    served and are recomputed on demand."""
    repo.save_profile(db, profile)
    repo.delete_artifacts(db, profile.profile_id, *STALE_ON_PROFILE_CHANGE)


def stored_jobs(db: Session, profile: MasterProfile) -> list[Job]:
    return [Job(**a.data) for a in repo.list_artifacts(db, profile.profile_id, "job")]


def get_job(db: Session, profile: MasterProfile, job_id: str) -> Job:
    artifact = repo.get_artifact(db, profile.profile_id, "job", job_id)
    if artifact is None:
        raise HTTPException(404, "Job not found.")
    return Job(**artifact.data)


def store_discovery(db: Session, profile: MasterProfile, result: JobDiscoveryResult) -> None:
    for job in result.jobs:
        _put(db, profile, "job", job.model_dump(), job.id)
    if result.queries:
        _put(db, profile, "job_discovery", result.model_dump(include={"queries", "dropped"}))


def discover(db: Session, llm: LLM, profile: MasterProfile) -> JobDiscoveryResult:
    result = discover_jobs(llm, profile)
    store_discovery(db, profile, result)
    return result


def current_fits(db: Session, profile: MasterProfile) -> dict[str, dict]:
    return {
        a.ref: a.data
        for a in repo.list_artifacts(db, profile.profile_id, "fit_report")
        if a.profile_version == profile.version
    }


def score_pending(
    db: Session, llm: LLM, profile: MasterProfile, job_ids: list[str] | None = None
) -> tuple[dict[str, dict], list[str]]:
    """Score every job (or the named ones) that has no current report. Returns all current
    reports by job id, and the ids that failed."""
    done = current_fits(db, profile)
    todo = [
        job
        for job in stored_jobs(db, profile)
        if job.id not in done and (job_ids is None or job.id in job_ids)
    ]
    failed = []
    for job_id, report in score_jobs(llm, profile, todo).items():
        if report is None:
            failed.append(job_id)
            continue
        done[job_id] = report.model_dump()
        _put(db, profile, "fit_report", done[job_id], job_id)
    return done, failed


def tailor_job(db: Session, llm: LLM, profile: MasterProfile, job_id: str) -> TailorResult:
    job = get_job(db, profile, job_id)
    fit = current(db, profile, "fit_report", job_id)
    if fit is None:
        report = score_job(llm, profile, job)
        _put(db, profile, "fit_report", report.model_dump(), job_id)
    else:
        report = FitReport(**fit)

    result = tailor_resume(llm, profile, job, report)
    if result.status == "tailored":
        try:
            if render.page_count(render.render_html(profile, result.resume)) > 1:
                feedback = {
                    "render_feedback": "The rendered resume spilled onto a second page. Cut the "
                    "least relevant content harder; it must fit one page."
                }
                result = tailor_resume(llm, profile, job, report, feedback)
        except render.PdfUnavailable:
            pass  # no renderer on this machine, so no page count; the PDF route reports it
    _put(db, profile, "tailored_resume", result.model_dump(), job_id)
    return result


def stored_tailoring(db: Session, profile: MasterProfile, job_id: str) -> TailorResult:
    data = current(db, profile, "tailored_resume", job_id)
    if data is None:
        raise HTTPException(404, "No tailored resume for this job yet.")
    return TailorResult(**data)


def scored_pairs(db: Session, profile: MasterProfile) -> list[tuple[Job, FitReport]]:
    fits = current_fits(db, profile)
    return [(j, FitReport(**fits[j.id])) for j in stored_jobs(db, profile) if j.id in fits]


def run_coach(db: Session, llm: LLM, profile: MasterProfile) -> CoachingPlan:
    scored = scored_pairs(db, profile)
    if not scored:
        raise HTTPException(409, "Score some jobs first: the coach works from fit reports.")
    plan = coach(llm, profile, scored)
    _put(db, profile, "coaching_plan", plan.model_dump())
    return plan


def run_linkedin(
    db: Session, llm: LLM, profile: MasterProfile, linkedin_text: str
) -> LinkedInOptimizationResult:
    result = optimize_linkedin(llm, profile, linkedin_text)
    _put(db, profile, "linkedin", result.model_dump())
    return result


def stale_resume_labels(db: Session, profile: MasterProfile) -> list[str]:
    """The jobs whose tailored resume a profile change would invalidate."""
    jobs = {j.id: job_label(j) for j in stored_jobs(db, profile)}
    tailored = repo.list_artifacts(db, profile.profile_id, "tailored_resume")
    return [jobs.get(a.ref, a.ref) for a in tailored]


def open_gaps(db: Session, profile: MasterProfile) -> list[str]:
    """Skills some current fit report lists as missing, most frequent first."""
    counts: dict[str, int] = {}
    for report in current_fits(db, profile).values():
        for missing in report["missing"]:
            counts[missing["skill"]] = counts.get(missing["skill"], 0) + 1
    return sorted(counts, key=lambda skill: -counts[skill])
