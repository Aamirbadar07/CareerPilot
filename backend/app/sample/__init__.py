"""The built-in sample candidate (fictional). Seeds demo mode and doubles as the fixture set
for agent tests. The JSON files here are hand-authored to the agents' output contracts; they
are not recordings of model output."""

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.db import repositories as repo
from app.schemas.profile import MasterProfile

SAMPLE_ID = "sample"
_DIR = Path(__file__).parent


def load(name: str) -> dict:
    return json.loads((_DIR / name).read_text(encoding="utf-8"))


def text(name: str) -> str:
    return (_DIR / name).read_text(encoding="utf-8")


def seed(db: Session) -> None:
    """Insert the sample profile and its artifacts once."""
    if repo.get_profile(db, SAMPLE_ID) is not None:
        return
    analysis = load("analysis.json")
    profile = MasterProfile.model_validate(analysis.pop("master_profile"))
    repo.save_profile(db, profile)  # no ttl: never expires
    repo.put_artifact(db, SAMPLE_ID, "resume_analysis", analysis, profile.version)
