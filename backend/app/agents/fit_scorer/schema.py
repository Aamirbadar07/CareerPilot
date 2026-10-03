from typing import Literal

from pydantic import BaseModel, Field

WEIGHTS = [35, 10, 20, 20, 10, 5]
MUST_HAVE_CAP = 60


def band_for(score: int) -> str:
    """The prompt's LIKELIHOOD table. Applied in code so a band can never disagree with
    its score."""
    if score >= 75:
        return "Strong"
    if score >= 55:
        return "Competitive"
    if score >= 35:
        return "Stretch"
    return "Poor"


class Dimension(BaseModel):
    name: str
    score: int
    max: int
    why: str


class Matched(BaseModel):
    skill: str
    evidence: str


class Missing(BaseModel):
    skill: str
    type: Literal["blocker", "learnable"]
    how_to_close: str


class FitReport(BaseModel):
    score: int
    band: str
    dimensions: list[Dimension]
    matched: list[Matched] = []
    missing: list[Missing] = []
    closable_now: list[str] = []
    resume_angle: str
    application_priority: int = Field(ge=1, le=5)
    verdict: str
    capped: bool = False  # set by code: a missing must-have held the score at 60
