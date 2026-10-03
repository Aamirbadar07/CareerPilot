from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.agents.fit_scorer.agent import score_job
from app.agents.fit_scorer.schema import FitReport
from app.agents.job_discovery.schema import Job
from app.agents.resume_tailor.agent import tailor_resume, untailored
from app.agents.resume_tailor.schema import TailorResult
from app.api.deps import get_llm, get_profile
from app.core import render
from app.core.llm import LLM
from app.core.rate_limit import rate_limit
from app.db import repositories as repo
from app.db.session import get_db
from app.schemas.profile import MasterProfile

router = APIRouter(prefix="/api/profiles/{profile_id}/jobs/{job_id}/tailor")


def _job(db: Session, profile: MasterProfile, job_id: str) -> Job:
    artifact = repo.get_artifact(db, profile.profile_id, "job", job_id)
    if artifact is None:
        raise HTTPException(404, "Job not found.")
    return Job(**artifact.data)


def _stored(db: Session, profile: MasterProfile, job_id: str) -> TailorResult:
    """The tailored resume for the current profile version. One built from an older version
    is stale and is not served: tailored resumes always regenerate from the latest profile."""
    artifact = repo.get_artifact(db, profile.profile_id, "tailored_resume", job_id)
    if artifact is None or artifact.profile_version != profile.version:
        raise HTTPException(404, "No tailored resume for this job yet.")
    return TailorResult(**artifact.data)


@router.post("", dependencies=[Depends(rate_limit(20, 3600))])
def tailor(
    job_id: str,
    profile: MasterProfile = Depends(get_profile),
    db: Session = Depends(get_db),
    llm: LLM = Depends(get_llm),
):
    """Tailor the resume to one job the user picked. Never runs unasked."""
    job = _job(db, profile, job_id)
    fit = repo.get_artifact(db, profile.profile_id, "fit_report", job_id)
    if fit is not None and fit.profile_version == profile.version:
        report = FitReport(**fit.data)
    else:
        report = score_job(llm, profile, job)
        repo.put_artifact(
            db, profile.profile_id, "fit_report", report.model_dump(), profile.version, job_id
        )

    result = tailor_resume(llm, profile, job, report)
    if result.status == "tailored":
        try:
            if render.page_count(render.render_html(profile, result.resume)) > 1:
                feedback = {
                    "render_feedback": "The rendered resume spilled onto a second page. Cut the "
                    "least relevant content harder; it must fit one page."
                }
                result = tailor_resume(llm, profile, job, report, feedback)
        except render.PdfUnavailable:
            pass  # no renderer on this machine, so no page count; the PDF route reports it
    repo.put_artifact(
        db, profile.profile_id, "tailored_resume", result.model_dump(), profile.version, job_id
    )
    return {"result": result, "original": untailored(profile)}


@router.get("")
def read(job_id: str, profile: MasterProfile = Depends(get_profile), db: Session = Depends(get_db)):
    """The tailored resume and the untouched original, for the side-by-side diff."""
    return {"result": _stored(db, profile, job_id), "original": untailored(profile)}


@router.get("/html")
def html(job_id: str, profile: MasterProfile = Depends(get_profile), db: Session = Depends(get_db)):
    resume = _stored(db, profile, job_id).resume
    return Response(render.render_html(profile, resume), media_type="text/html")


@router.get("/pdf")
def pdf(job_id: str, profile: MasterProfile = Depends(get_profile), db: Session = Depends(get_db)):
    resume = _stored(db, profile, job_id).resume
    try:
        _, page = render.fit_to_one_page(profile, resume)
        data = render.render_pdf(page)
    except render.PdfUnavailable:
        raise HTTPException(
            501, "PDF rendering is not available on this server. Use the HTML preview and print it."
        ) from None
    name = (profile.identity.full_name or "resume").replace(" ", "_")
    headers = {"Content-Disposition": f'attachment; filename="{name}_resume.pdf"'}
    return Response(data, media_type="application/pdf", headers=headers)
