"""LinkedIn copy and the coaching plan: the two agents that advise rather than apply."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import services
from app.api.deps import get_llm, get_own_profile, get_profile
from app.core.llm import LLM
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.schemas.profile import MasterProfile

router = APIRouter(prefix="/api/profiles/{profile_id}")


class LinkedInText(BaseModel):
    linkedin_text: str = Field(min_length=50, max_length=30_000)


@router.post("/linkedin", dependencies=[Depends(rate_limit(10, 3600))])
def optimize_linkedin(
    body: LinkedInText,
    profile: MasterProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
    llm: LLM = Depends(get_llm),
):
    """Copy-paste-ready LinkedIn text from the profile the user pasted. Nothing is posted."""
    return services.run_linkedin(db, llm, profile, body.linkedin_text)


@router.get("/linkedin")
def read_linkedin(profile: MasterProfile = Depends(get_profile), db: Session = Depends(get_db)):
    return {"result": services.current(db, profile, "linkedin")}


@router.post("/coach", dependencies=[Depends(rate_limit(10, 3600))])
def run_coach(
    profile: MasterProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
    llm: LLM = Depends(get_llm),
):
    return services.run_coach(db, llm, profile)


@router.get("/coach")
def read_coach(profile: MasterProfile = Depends(get_profile), db: Session = Depends(get_db)):
    return {"plan": services.current(db, profile, "coaching_plan")}
