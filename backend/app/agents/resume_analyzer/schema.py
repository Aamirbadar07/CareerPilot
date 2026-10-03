from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, model_validator

from app.schemas.profile import MasterProfile


class AtsComponent(BaseModel):
    name: str
    score: int
    max: int
    why: str


class Ats(BaseModel):
    score: int
    components: list[AtsComponent]


class WeakBullet(BaseModel):
    bullet_id: str
    problem: str
    rewrite: str
    needs_from_user: str | None = None


class MissingKeyword(BaseModel):
    keyword: str
    for_role: str
    severity: Literal["high", "medium", "low"]


class SupportedRole(BaseModel):
    title: str
    confidence: float
    evidence: list[str]


class Gap(BaseModel):
    gap: str
    blocks: str
    smallest_action: str


def profile_ids(profile: MasterProfile) -> tuple[set[str], set[str]]:
    """(every id that can serve as evidence, bullet ids only)."""
    bullets = {b.id for e in profile.experience for b in e.bullets}
    bullets |= {b.id for p in profile.projects for b in p.bullets}
    owners = {e.id for e in profile.experience} | {p.id for p in profile.projects}
    return bullets | owners | {c.id for c in profile.certifications}, bullets


class ResumeAnalysisResult(BaseModel):
    master_profile: MasterProfile
    ats: Ats
    weak_bullets: list[WeakBullet]
    missing_keywords: list[MissingKeyword]
    target_roles: list[SupportedRole]
    top_gaps: list[Gap]
    overall_verdict: str

    @model_validator(mode="before")
    @classmethod
    def _code_owns_identity(cls, data):
        """Ids, versions and provenance are assigned by code, whatever the model wrote."""
        if isinstance(data, dict) and isinstance(data.get("master_profile"), dict):
            profile = data["master_profile"]
            profile.setdefault("profile_id", "pending")
            profile.setdefault("version", 1)
            profile.setdefault("updated_at", datetime.now(UTC).isoformat())
            profile.pop("provenance", None)
        return data

    @model_validator(mode="after")
    def _no_unsupported_claims(self):
        """The no-fabrication rule, checked in code. Messages name positions, never content,
        because they are fed back to the model and may reach logs."""
        evidence_ids, bullet_ids = profile_ids(self.master_profile)
        for i, skill in enumerate(self.master_profile.skills):
            if not evidence_ids.intersection(skill.evidence):
                raise ValueError(f"skills[{i}] has no evidence id that exists in the profile")
        for i, weak in enumerate(self.weak_bullets):
            if weak.bullet_id not in bullet_ids:
                raise ValueError(f"weak_bullets[{i}].bullet_id is not a bullet in the profile")
        self.ats.score = sum(c.score for c in self.ats.components)  # arithmetic is ours
        return self
