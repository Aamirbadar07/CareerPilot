from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import services
from app.agents.credentials.agent import propose_credential
from app.agents.credentials.schema import CredentialProposal
from app.api.deps import get_llm, get_own_profile, get_profile
from app.api.profiles import read_upload
from app.core.llm import LLM
from app.core.profile_ops import apply_credential
from app.core.rate_limit import rate_limit
from app.db import repositories as repo
from app.db.session import get_db
from app.schemas.profile import MasterProfile

router = APIRouter(prefix="/api/profiles/{profile_id}/credentials")
KIND = "credential_proposal"


@router.post("", dependencies=[Depends(rate_limit(20, 3600))])
def propose(
    file: UploadFile | None = None,
    url: str | None = Form(default=None, max_length=500),
    statement: str | None = Form(default=None, max_length=2000),
    profile: MasterProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
    llm: LLM = Depends(get_llm),
):
    """Read a certificate, a credential link or a short statement, and return what would be
    added. Nothing is written to the profile here. The link is passed to the model as text;
    the app does not fetch it."""
    if file is not None:
        _, evidence = read_upload(file)
        source = "upload"
    elif url:
        evidence, source = statement or "", "link"
    elif statement:
        evidence, source = statement, "manual"
    else:
        raise HTTPException(422, "Send a certificate file, a credential URL or a statement.")

    proposal = propose_credential(
        llm,
        profile,
        evidence,
        url,
        source,
        stale_resumes=services.stale_resume_labels(db, profile),
        open_gaps=services.open_gaps(db, profile),
    )
    proposal_id = uuid4().hex[:12]
    repo.put_artifact(
        db, profile.profile_id, KIND, proposal.model_dump(), profile.version, proposal_id
    )
    return {"proposal_id": proposal_id, "proposal": proposal}


@router.post("/{proposal_id}/confirm")
def confirm(
    proposal_id: str,
    profile: MasterProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
):
    """The user approved: write the certification as a new profile version and drop the
    tailored resumes and coaching plan that the old version produced."""
    artifact = repo.get_artifact(db, profile.profile_id, KIND, proposal_id)
    if artifact is None:
        raise HTTPException(404, "No such proposal. It may already have been confirmed.")
    if artifact.profile_version != profile.version:
        raise HTTPException(409, "The profile changed since this was proposed. Submit it again.")
    updated = apply_credential(profile, CredentialProposal(**artifact.data))
    services.save_new_version(db, updated)
    repo.delete_artifacts(db, profile.profile_id, KIND)
    return {"profile": updated}


@router.delete("/{proposal_id}", status_code=204)
def reject(
    proposal_id: str,
    profile: MasterProfile = Depends(get_own_profile),
    db: Session = Depends(get_db),
):
    artifact = repo.get_artifact(db, profile.profile_id, KIND, proposal_id)
    if artifact is not None:
        db.delete(artifact)
        db.commit()


@router.get("")
def history(profile: MasterProfile = Depends(get_profile), db: Session = Depends(get_db)):
    return {
        "certifications": profile.certifications,
        "history": [c for c in profile.provenance.change_log if c.agent == "credentials"],
        "pending": [
            {"proposal_id": a.ref, "proposal": a.data}
            for a in repo.list_artifacts(db, profile.profile_id, KIND)
            if a.profile_version == profile.version
        ],
    }
