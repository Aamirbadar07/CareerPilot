from typing import Literal

from pydantic import BaseModel, ConfigDict


class _Strict(BaseModel):
    # numbers-to-str: a model may emit a CGPA or a metric as a bare number
    model_config = ConfigDict(extra="forbid", coerce_numbers_to_str=True)


class Identity(_Strict):
    full_name: str | None = None
    title_line: str | None = None
    location: str | None = None
    email: str | None = None
    phone: str | None = None
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None


class Skill(_Strict):
    name: str
    category: str
    evidence: list[str] = []
    level: str | None = None
    first_seen: str | None = None
    verified: bool = False


class Bullet(_Strict):
    id: str
    text: str
    skills: list[str] = []
    metric: str | None = None
    impact_verb: str | None = None


class ProjectBullet(_Strict):
    id: str
    text: str
    skills: list[str] = []


class Experience(_Strict):
    id: str
    company: str
    role: str
    employment_type: str | None = None
    location: str | None = None
    remote: bool | None = None
    start: str | None = None
    end: str | None = None
    current: bool = False
    bullets: list[Bullet] = []
    tech: list[str] = []


class Project(_Strict):
    id: str
    name: str
    one_liner: str | None = None
    bullets: list[ProjectBullet] = []
    tech: list[str] = []
    repo_url: str | None = None
    live_url: str | None = None
    date: str | None = None


class Education(_Strict):
    degree: str | None = None
    field: str | None = None
    institution: str | None = None
    start: str | None = None
    end: str | None = None
    score: str | None = None
    score_type: str | None = None


class Certification(_Strict):
    id: str
    name: str
    issuer: str | None = None
    issued: str | None = None
    expires: str | None = None
    credential_id: str | None = None
    credential_url: str | None = None
    skills_covered: list[str] = []
    verified: bool = False
    source: Literal["upload", "link", "manual"]


class Achievement(_Strict):
    text: str
    date: str | None = None


class TargetRole(_Strict):
    title: str
    seniority: str | None = None
    keywords: list[str] = []
    priority: int = 1


class Preferences(_Strict):
    remote_only: bool = False
    locations: list[str] = []
    min_salary: int | None = None
    currency: str = "INR"
    employment_types: list[str] = []
    exclude_companies: list[str] = []


class ChangeLogEntry(_Strict):
    version: int
    agent: str
    change: str
    at: str
    approved_by_user: bool


class Provenance(_Strict):
    source_file: str | None = None
    parsed_at: str | None = None
    change_log: list[ChangeLogEntry] = []


class MasterProfile(_Strict):
    profile_id: str
    version: int
    updated_at: str
    identity: Identity
    summary_source: str | None = None
    skills: list[Skill] = []
    experience: list[Experience] = []
    projects: list[Project] = []
    education: list[Education] = []
    certifications: list[Certification] = []
    achievements: list[Achievement] = []
    target_roles: list[TargetRole] = []
    preferences: Preferences = Preferences()
    provenance: Provenance = Provenance()
