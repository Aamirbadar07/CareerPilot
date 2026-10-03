from datetime import timedelta
from pathlib import PurePath

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.agents.resume_analyzer.agent import analyze_resume
from app.api.deps import get_llm, get_profile
from app.core.config import settings
from app.core.llm import LLM
from app.core.rate_limit import rate_limit
from app.core.resume_text import MAX_UPLOAD_BYTES, UnreadableResume, extract_text
from app.db import repositories as repo
from app.db.session import get_db
from app.sample import SAMPLE_ID
from app.schemas.profile import MasterProfile

router = APIRouter(prefix="/api")


@router.post("/resume", dependencies=[Depends(rate_limit(5, 3600))])
def upload_resume(file: UploadFile, db: Session = Depends(get_db), llm: LLM = Depends(get_llm)):
    """Parse and analyse a resume. The file lives only in memory for this request."""
    repo.purge_expired(db)  # ponytail: purge rides on uploads; add a scheduled job if they are rare
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    file.file.close()
    name = PurePath(file.filename or "resume").name
    try:
        text = extract_text(name, data)
    except UnreadableResume as e:
        raise HTTPException(422, str(e)) from None
    result = analyze_resume(llm, text, name)

    profile = result.master_profile
    repo.save_profile(db, profile, ttl=timedelta(hours=settings.profile_ttl_hours))
    analysis = result.model_dump(exclude={"master_profile"})
    repo.put_artifact(db, profile.profile_id, "resume_analysis", analysis, profile.version)
    return {"profile": profile, "analysis": analysis}


@router.get("/profiles/{profile_id}")
def read_profile(profile: MasterProfile = Depends(get_profile), db: Session = Depends(get_db)):
    analysis = repo.get_artifact(db, profile.profile_id, "resume_analysis")
    return {"profile": profile, "analysis": analysis.data if analysis else None}


@router.delete("/profiles/{profile_id}", status_code=204)
def delete_my_data(profile_id: str, db: Session = Depends(get_db)):
    if profile_id == SAMPLE_ID:
        raise HTTPException(403, "The sample profile is shared and cannot be deleted.")
    repo.delete_profile(db, profile_id)
