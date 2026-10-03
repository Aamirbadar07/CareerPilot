from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.fit_scorer.agent import score_jobs
from app.agents.job_discovery.agent import discover_jobs, job_from_text
from app.agents.job_discovery.schema import Job, JobDiscoveryResult
from app.api.deps import get_llm, get_profile
from app.core.llm import LLM
from app.core.rate_limit import rate_limit
from app.db import repositories as repo
from app.db.session import get_db
from app.schemas.profile import MasterProfile

router = APIRouter(prefix="/api/profiles/{profile_id}/jobs")


def store_discovery(db: Session, profile: MasterProfile, result: JobDiscoveryResult) -> None:
    for job in result.jobs:
        repo.put_artifact(db, profile.profile_id, "job", job.model_dump(), profile.version, job.id)
    if result.queries:
        meta = result.model_dump(include={"queries", "dropped"})
        repo.put_artifact(db, profile.profile_id, "job_discovery", meta, profile.version)


@router.post("/discover", dependencies=[Depends(rate_limit(10, 3600))])
def discover(
    profile: MasterProfile = Depends(get_profile),
    db: Session = Depends(get_db),
    llm: LLM = Depends(get_llm),
):
    result = discover_jobs(llm, profile)
    store_discovery(db, profile, result)
    return result


class PastedJob(BaseModel):
    text: str = Field(min_length=200, max_length=20_000)
    url: str | None = Field(default=None, max_length=500)


@router.post("/paste", dependencies=[Depends(rate_limit(30, 3600))])
def paste(
    body: PastedJob,
    profile: MasterProfile = Depends(get_profile),
    db: Session = Depends(get_db),
    llm: LLM = Depends(get_llm),
):
    """Add a job from pasted text: the route for sites the app must not scrape."""
    result = job_from_text(llm, profile, body.text, body.url)
    if not result.jobs:
        reason = result.dropped[0].reason if result.dropped else "no job found in the text"
        raise HTTPException(422, f"Not added: {reason}")
    store_discovery(db, profile, result)
    return result.jobs[0]


def current_fits(db: Session, profile: MasterProfile) -> dict[str, dict]:
    """Fit reports computed against the current profile version, by job id. A report from an
    older version is stale: the profile changed, so the score may have too."""
    return {
        a.ref: a.data
        for a in repo.list_artifacts(db, profile.profile_id, "fit_report")
        if a.profile_version == profile.version
    }


def stored_jobs(db: Session, profile: MasterProfile) -> list[Job]:
    return [Job(**a.data) for a in repo.list_artifacts(db, profile.profile_id, "job")]


class FitRequest(BaseModel):
    job_ids: list[str] | None = None  # None = every job without a current report


@router.post("/fit", dependencies=[Depends(rate_limit(20, 3600))])
def fit(
    body: FitRequest,
    profile: MasterProfile = Depends(get_profile),
    db: Session = Depends(get_db),
    llm: LLM = Depends(get_llm),
):
    """Score jobs against the profile. Cached per (profile version, job)."""
    done = current_fits(db, profile)
    todo = [
        job
        for job in stored_jobs(db, profile)
        if job.id not in done and (body.job_ids is None or job.id in body.job_ids)
    ]
    failed = []
    for job_id, report in score_jobs(llm, profile, todo).items():
        if report is None:
            failed.append(job_id)
            continue
        done[job_id] = report.model_dump()
        repo.put_artifact(
            db, profile.profile_id, "fit_report", done[job_id], profile.version, job_id
        )
    return {"fits": done, "failed": failed}


@router.get("")
def list_jobs(profile: MasterProfile = Depends(get_profile), db: Session = Depends(get_db)):
    meta = repo.get_artifact(db, profile.profile_id, "job_discovery")
    fits = current_fits(db, profile)
    return {
        "jobs": [job.model_dump() | {"fit": fits.get(job.id)} for job in stored_jobs(db, profile)],
        "discovery": meta.data if meta else None,
    }
