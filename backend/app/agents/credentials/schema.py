from typing import Literal

from pydantic import BaseModel

from app.schemas.profile import Certification


class ExtractedCertification(BaseModel):
    """What the model read off the evidence. Ids and the verified flag are not its to set."""

    name: str
    issuer: str | None = None
    issued: str | None = None  # YYYY-MM
    expires: str | None = None
    credential_id: str | None = None
    credential_url: str | None = None


class ProfilePatch(BaseModel):
    op: Literal["add", "update"]
    path: Literal["certifications"] = "certifications"
    value: Certification


class Downstream(BaseModel):
    roles_strengthened: list[str] = []
    gaps_closed: list[str] = []
    stale_resumes: list[str] = []


class CredentialExtraction(BaseModel):
    """The model's output. Fields the prompt asks for but code decides are accepted and
    then overwritten in the agent."""

    certification: ExtractedCertification
    skills_covered: list[str] = []
    duplicate_of: str | None = None
    needs_review: list[str] = []
    downstream: Downstream = Downstream()


class CredentialProposal(BaseModel):
    """What the user is asked to approve. Nothing is written until they do."""

    certification: Certification
    skills_covered: list[str]
    verified: bool
    duplicate_of: str | None
    needs_review: list[str]
    profile_patch: ProfilePatch
    downstream: Downstream
    confirmation_prompt: str
    linkedin_add_url: str
