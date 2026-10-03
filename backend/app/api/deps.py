from functools import lru_cache

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.llm import LLM
from app.db import repositories as repo
from app.db.session import SessionLocal, get_db
from app.sample import SAMPLE_ID
from app.schemas.profile import MasterProfile


@lru_cache
def get_llm() -> LLM:
    return LLM(cache=repo.DbCache(SessionLocal))


def get_profile(profile_id: str, db: Session = Depends(get_db)) -> MasterProfile:
    profile = repo.get_profile(db, profile_id)
    if profile is None:
        raise HTTPException(404, "Profile not found. It may have expired.")
    return profile


def get_own_profile(profile: MasterProfile = Depends(get_profile)) -> MasterProfile:
    """For routes that change a profile or spend model calls on new input. The sample profile
    is shared by every visitor, so it is read-only."""
    if profile.profile_id == SAMPLE_ID:
        raise HTTPException(
            403, "The sample profile is read-only. Upload your own resume to try this."
        )
    return profile
