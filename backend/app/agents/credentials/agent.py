import re
from typing import Literal
from urllib.parse import urlencode

from app.agents.credentials.prompt import SYSTEM_PROMPT
from app.agents.credentials.schema import (
    CredentialExtraction,
    CredentialProposal,
    Downstream,
    ProfilePatch,
)
from app.agents.fit_scorer.agent import profile_for_llm
from app.core.guard import norm
from app.core.llm import LLM
from app.schemas.profile import Certification, MasterProfile


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def linkedin_add_url(cert: Certification) -> str:
    """LinkedIn's pre-filled "add certification" link. The user opens it and saves the entry
    themselves; the app never writes to LinkedIn."""
    params = {"startTask": "CERTIFICATION_NAME", "name": cert.name}
    if cert.issuer:
        params["organizationName"] = cert.issuer
    for prefix, value in (("issue", cert.issued), ("expiration", cert.expires)):
        if value and re.fullmatch(r"\d{4}-\d{2}", value):
            params[f"{prefix}Year"], params[f"{prefix}Month"] = value[:4], str(int(value[5:]))
    if cert.credential_url:
        params["certUrl"] = cert.credential_url
    if cert.credential_id:
        params["certId"] = cert.credential_id
    return "https://www.linkedin.com/profile/add?" + urlencode(params)


def propose_credential(
    llm: LLM,
    profile: MasterProfile,
    evidence: str,
    url: str | None,
    source: Literal["upload", "link", "manual"],
    stale_resumes: list[str] = (),
    open_gaps: list[str] = (),
) -> CredentialProposal:
    """Read the evidence and build the patch the user will be asked to approve.

    The model extracts; code decides everything that must be exact: the id, whether the
    credential counts as verified, duplicates, the confirmation sentence and the LinkedIn link.
    `stale_resumes` and `open_gaps` come from stored data, not from the model."""
    extraction = llm.complete(
        SYSTEM_PROMPT,
        {
            "credential_artifact": {"kind": source, "text": evidence, "url": url},
            "master_profile": profile_for_llm(profile),
        },
        CredentialExtraction,
        profile_id=profile.profile_id,
    )
    found = extraction.certification
    haystack = _squash(f"{evidence} {url or ''}")
    needs_review = list(extraction.needs_review)

    # A value the evidence does not contain was guessed. Ids and URLs are dropped outright,
    # because they decide `verified`; names are kept but flagged for the user.
    credential_id = found.credential_id
    if credential_id and _squash(credential_id) not in haystack:
        credential_id = None
        needs_review.append("credential_id")
    credential_url = url or found.credential_url
    if credential_url and _squash(credential_url) not in haystack:
        credential_url = None
        needs_review.append("credential_url")
    for field in ("name", "issuer"):
        value = getattr(found, field)
        if value and _squash(value) not in haystack:
            needs_review.append(field)

    existing = {c.id: c for c in profile.certifications}
    duplicate_of = extraction.duplicate_of if extraction.duplicate_of in existing else None
    if duplicate_of is None:
        duplicate_of = next(
            (c.id for c in existing.values() if norm(c.name) == norm(found.name)), None
        )
    numbers = [int(i[5:]) for i in existing if re.fullmatch(r"cert_\d+", i)]
    cert = Certification(
        id=duplicate_of or f"cert_{max(numbers, default=0) + 1}",
        name=found.name,
        issuer=found.issuer,
        issued=found.issued,
        expires=found.expires,
        credential_id=credential_id,
        credential_url=credential_url,
        skills_covered=extraction.skills_covered,
        verified=bool(credential_id or credential_url),
        source=source,
    )

    covered = {norm(s) for s in extraction.skills_covered}
    roles = {r.title for r in profile.target_roles}
    downstream = Downstream(
        roles_strengthened=[r for r in extraction.downstream.roles_strengthened if r in roles],
        gaps_closed=[
            g for g in open_gaps if any(s and f" {s} " in f" {norm(g)} " for s in covered)
        ],
        stale_resumes=list(stale_resumes),
    )
    label, article = ("verified", "a") if cert.verified else ("unverified", "an")
    details = ", ".join(x for x in (cert.issuer, cert.issued) if x)
    skills = ", ".join(cert.skills_covered) or "no skills"
    action = f"Update {duplicate_of} to" if duplicate_of else "Add"
    return CredentialProposal(
        certification=cert,
        skills_covered=cert.skills_covered,
        verified=cert.verified,
        duplicate_of=duplicate_of,
        needs_review=sorted(set(needs_review)),
        profile_patch=ProfilePatch(op="update" if duplicate_of else "add", value=cert),
        downstream=downstream,
        confirmation_prompt=f'{action} "{cert.name}"{f" ({details})" if details else ""} '
        f"as {article} {label} certification covering: {skills}.",
        linkedin_add_url=linkedin_add_url(cert),
    )
