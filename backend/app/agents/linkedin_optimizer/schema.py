from typing import Literal

from pydantic import BaseModel, Field


class ExperienceRewrite(BaseModel):
    exp_id: str
    scope: str
    bullets: list[str]


class SkillOrder(BaseModel):
    name: str
    pinned: bool = False


class KeywordGap(BaseModel):
    term: str
    status: Literal["addable-now", "needs-work"]
    note: str = ""


class Mismatch(BaseModel):
    field: str
    resume_value: str | None = None
    linkedin_value: str | None = None
    correct_value: str


class StrengthComponent(BaseModel):
    name: str
    score: int
    max: int
    why: str


class ProfileStrength(BaseModel):
    score: int
    components: list[StrengthComponent]
    top_changes: list[str]


class FeaturedSuggestion(BaseModel):
    item: str
    why: str


class LinkedInOptimizationResult(BaseModel):
    headline: list[str] = Field(min_length=3, max_length=3)
    about: list[str] = Field(min_length=4, max_length=6)
    experience_rewrites: list[ExperienceRewrite]
    skills_order: list[SkillOrder] = Field(max_length=50)
    keyword_gaps: list[KeywordGap] = []
    consistency_check: list[Mismatch] = []
    profile_strength: ProfileStrength
    featured_suggestions: list[FeaturedSuggestion] = []
