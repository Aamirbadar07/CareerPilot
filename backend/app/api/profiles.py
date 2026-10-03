from pathlib import PurePath

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import services
from app.api.deps import get_llm, get_own_profile, get_profile
from app.core.llm import LLM
from app.core.profile_ops import bump
from app.core.rate_limit import rate_limit
from app.core.resume_text import MAX_UPLOAD_BYTES, UnreadableResume, extract_text
from app.db import repositories as repo
from app.db.session import get_db
from app.sample import SAMPLE_ID
from app.schemas.profile import MasterProfile, Preferences

router = APIRouter(prefix="/api")


def read_upload(file: UploadFile) -> tuple[str, str]:
    """(safe file name, extracted text). The upload lives only in memory for this request."""
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    file.file.close()
    name = PurePath(file.filename or "resume").name
    try:
        return name, extract_text(name, data)
    except UnreadableResume as e:
        raise HTTPException(422, str(e)) from None


@router.post("/resume", dependencies=[Depends(rate_limit(5, 3600))])
def upload_resume(file: UploadFile, db: Session = Depends(get_db), llm: LLM = Depends(get_llm)):
    """Parse and analyse a resume without running the rest of the pipeline."""
    repo.purge_expired(db)  # ponytail: purge rides on uploads; add a scheduled job if they are rare
    name, text = read_upload(file)
    result = services.ingest_resume(db, llm, text, name)
    return {
        "profile": result.master_profile,
        "analysis": result.model_dump(exclude={"master_profile"}),
    }


@router.get("/profiles/{profile_id}")
def read_profile(profile: MasterProfile = Depends(get_profile), db: Session = Depends(get_db)):
    analysis = repo.get_artifact(db, profile.profile_id, "resume_analysis")
    expires = db.get(repo.Profile, profile.profile_id).expires_at
    return {
        "profile": profile,
        "analysis": analysis.data if analysis else None,
        "expires_at": expires,
        "is_sample": profile.profile_id == SAMPLE_ID,
    }


@router.put("/profiles/{profile_id}/preferences")
def update_preferences(
    preferences: Preferences,
    profile: MasterProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
):
    """The user edits their own search preferences: a new profile version, like any change."""
    profile.preferences = preferences
    services.save_new_version(db, bump(profile, "user", "updated preferences"))
    return profile


@router.delete("/profiles/{profile_id}", status_code=204)
def delete_my_data(
    profile: MasterProfile = Depends(get_own_profile), db: Session = Depends(get_db)
):
    repo.delete_profile(db, profile.profile_id)
