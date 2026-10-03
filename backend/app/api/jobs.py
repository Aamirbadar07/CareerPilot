from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.job_discovery.agent import discover_jobs, job_from_text
from app.agents.job_discovery.schema import JobDiscoveryResult
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


@router.get("")
def list_jobs(profile: MasterProfile = Depends(get_profile), db: Session = Depends(get_db)):
    meta = repo.get_artifact(db, profile.profile_id, "job_discovery")
    return {
        "jobs": [a.data for a in repo.list_artifacts(db, profile.profile_id, "job")],
        "discovery": meta.data if meta else None,
    }
