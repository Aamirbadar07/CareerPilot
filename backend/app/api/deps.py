from functools import lru_cache

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.llm import LLM
from app.db import repositories as repo
from app.db.session import SessionLocal, get_db
from app.schemas.profile import MasterProfile


@lru_cache
def get_llm() -> LLM:
    return LLM(cache=repo.DbCache(SessionLocal))


def get_profile(profile_id: str, db: Session = Depends(get_db)) -> MasterProfile:
    profile = repo.get_profile(db, profile_id)
    if profile is None:
        raise HTTPException(404, "Profile not found. It may have expired.")
    return profile
