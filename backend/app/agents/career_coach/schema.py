from typing import Literal

from pydantic import BaseModel, Field


class PatternGap(BaseModel):
    skill: str
    blocks_n_jobs: int
    pct_of_targets: int
    acquisition_difficulty: Literal["low", "medium", "high"]


class ScoreCeiling(BaseModel):
    change: str
    jobs_moved: list[str] = []
    expected_band_shift: str = ""


class Positioning(BaseModel):
    verdict: str
    commit_to: list[str] = []
    drop: list[str] = []


class EvidenceDebt(BaseModel):
    skill: str
    risk: str


class Action(BaseModel):
    rank: int
    action: str
    why_this_one: str
    effort_hours: float
    cost: str
    timeline: Literal["this week", "this month", "this quarter"]
    proof_artifact: str
    jobs_unlocked: list[str] = []


class CoachingPlan(BaseModel):
    pattern_gaps: list[PatternGap] = []
    score_ceiling: ScoreCeiling
    positioning: Positioning
    evidence_debt: list[EvidenceDebt] = []
    plan: list[Action] = Field(min_length=5, max_length=5)
    one_line_verdict: str
