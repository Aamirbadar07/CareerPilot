from typing import Literal

from pydantic import BaseModel


class TailoredBullet(BaseModel):
    text: str
    from_bullet: str


class TailoredExperience(BaseModel):
    exp_id: str
    bullets: list[TailoredBullet]


class TailoredProject(BaseModel):
    proj_id: str
    bullets: list[TailoredBullet]


class SkillGroup(BaseModel):
    category: str
    items: list[str]


class Omitted(BaseModel):
    item: str
    why: str


class TailoredResume(BaseModel):
    title_line: str
    summary: str
    skills: list[SkillGroup]
    experience: list[TailoredExperience]
    projects: list[TailoredProject] = []
    omitted: list[Omitted] = []
    keywords_covered: list[str] = []
    keywords_not_covered: list[str] = []


class Finding(BaseModel):
    claim: str
    status: Literal["SUPPORTED", "REWORDED", "OVERSTATED", "UNSUPPORTED"]
    profile_evidence: str | None = None
    fix: str = ""

    @property
    def must_fix(self) -> bool:
        return self.status in ("OVERSTATED", "UNSUPPORTED")


class ValidationReport(BaseModel):
    verdict: Literal["pass", "fail"]
    findings: list[Finding]
    must_fix_count: int = 0


class TailorResult(BaseModel):
    status: Literal["tailored", "untailored"]
    resume: TailoredResume
    validation: ValidationReport | None = None
    attempts: int
    reason: str | None = None  # why the user got the untailored resume
