from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import services
from app.agents.job_discovery.agent import job_from_text
from app.api.deps import get_llm, get_own_profile, get_profile
from app.core.llm import LLM
from app.core.rate_limit import rate_limit
from app.db import repositories as repo
from app.db.session import get_db
from app.schemas.profile import MasterProfile

router = APIRouter(prefix="/api/profiles/{profile_id}/jobs")


@router.post("/discover", dependencies=[Depends(rate_limit(10, 3600))])
def discover(
    profile: MasterProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
    llm: LLM = Depends(get_llm),
):
    return services.discover(db, llm, profile)


class PastedJob(BaseModel):
    text: str = Field(min_length=200, max_length=20_000)
    url: str | None = Field(default=None, max_length=500)


@router.post("/paste", dependencies=[Depends(rate_limit(30, 3600))])
def paste(
    body: PastedJob,
    profile: MasterProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
    llm: LLM = Depends(get_llm),
):
    """Add a job from pasted text: the route for sites the app must not scrape."""
    result = job_from_text(llm, profile, body.text, body.url)
    if not result.jobs:
        reason = result.dropped[0].reason if result.dropped else "no job found in the text"
        raise HTTPException(422, f"Not added: {reason}")
    services.store_discovery(db, profile, result)
    return result.jobs[0]


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
    fits, failed = services.score_pending(db, llm, profile, body.job_ids)
    return {"fits": fits, "failed": failed}


@router.get("")
def list_jobs(profile: MasterProfile = Depends(get_profile), db: Session = Depends(get_db)):
    meta = repo.get_artifact(db, profile.profile_id, "job_discovery")
    fits = services.current_fits(db, profile)
    tailored = {a.ref for a in repo.list_artifacts(db, profile.profile_id, "tailored_resume")}
    return {
        "jobs": [
            job.model_dump() | {"fit": fits.get(job.id), "tailored": job.id in tailored}
            for job in services.stored_jobs(db, profile)
        ],
        "discovery": meta.data if meta else None,
    }


@router.get("/{job_id}")
def read_job(
    job_id: str, profile: MasterProfile = Depends(get_profile), db: Session = Depends(get_db)
):
    job = services.get_job(db, profile, job_id)
    return job.model_dump() | {"fit": services.current_fits(db, profile).get(job_id)}
