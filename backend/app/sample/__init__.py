"""The built-in sample candidate (fictional). Seeds demo mode and doubles as the fixture set
for agent tests. The JSON files here are hand-authored to the agents' output contracts; they
are not recordings of model output."""

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.agents.job_discovery.agent import job_id
from app.db import repositories as repo
from app.schemas.profile import MasterProfile

SAMPLE_ID = "sample"
_DIR = Path(__file__).parent


def load(name: str) -> dict:
    return json.loads((_DIR / name).read_text(encoding="utf-8"))


def text(name: str) -> str:
    return (_DIR / name).read_text(encoding="utf-8")


def profile() -> MasterProfile:
    return MasterProfile.model_validate(load("analysis.json")["master_profile"])


def jobs() -> list[dict]:
    """Sample jobs with the ids the pipeline would give them."""
    return [job | {"id": job_id(job["url"])} for job in load("jobs.json")["jobs"]]


def seed(db: Session) -> None:
    """Insert the sample profile once; refresh its artifacts on every start so a deploy with
    edited sample files shows them."""
    candidate = profile()
    if repo.get_profile(db, SAMPLE_ID) is None:
        repo.save_profile(db, candidate)  # no ttl: never expires

    def put(kind: str, data: dict, ref: str = "") -> None:
        repo.put_artifact(db, SAMPLE_ID, kind, data, candidate.version, ref)

    analysis = load("analysis.json")
    del analysis["master_profile"]
    put("resume_analysis", analysis)
    fits, tailored = load("fits.json"), load("tailored.json")
    for job in jobs():
        put("job", job, job["id"])
        put("fit_report", fits[job["url"]], job["id"])
        if job["url"] in tailored:
            put("tailored_resume", tailored[job["url"]], job["id"])
    discovery = load("jobs.json")
    del discovery["jobs"]
    put("job_discovery", discovery)
