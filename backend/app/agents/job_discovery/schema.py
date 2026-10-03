from pydantic import BaseModel


class Query(BaseModel):
    q: str
    source: str
    rationale: str = ""


class RawPosting(BaseModel):
    """One posting exactly as a source returned it, HTML stripped. Never model output."""

    url: str
    title: str
    company: str
    location: str | None = None
    posted: str | None = None  # YYYY-MM-DD
    source: str
    salary: str | None = None
    description: str = ""


class Job(BaseModel):
    id: str = ""
    title: str
    company: str
    location: str | None = None
    remote: bool | None = None
    posted: str | None = None
    url: str
    mirrors: list[str] = []
    source: str
    must_have: list[str] = []
    nice_to_have: list[str] = []
    years_required: float | str | None = None
    stack: list[str] = []
    employment_type: str | None = None
    salary: str | None = None
    description_excerpt: str = ""
    description: str = ""  # set by code from the source posting, for the fit scorer


class Dropped(BaseModel):
    title: str
    company: str
    reason: str


class JobDiscoveryResult(BaseModel):
    queries: list[Query] = []
    jobs: list[Job] = []
    dropped: list[Dropped] = []
