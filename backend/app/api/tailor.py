from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import services
from app.agents.resume_tailor.agent import untailored
from app.api.deps import get_llm, get_profile
from app.core import render
from app.core.llm import LLM
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.schemas.profile import MasterProfile

router = APIRouter(prefix="/api/profiles/{profile_id}/jobs/{job_id}/tailor")


@router.post("", dependencies=[Depends(rate_limit(20, 3600))])
def tailor(
    job_id: str,
    profile: MasterProfile = Depends(get_profile),
    db: Session = Depends(get_db),
    llm: LLM = Depends(get_llm),
):
    """Tailor the resume to one job the user picked. Never runs unasked."""
    result = services.tailor_job(db, llm, profile, job_id)
    return {"result": result, "original": untailored(profile)}


@router.get("")
def read(job_id: str, profile: MasterProfile = Depends(get_profile), db: Session = Depends(get_db)):
    """The tailored resume and the untouched original, for the side-by-side diff."""
    result = services.stored_tailoring(db, profile, job_id)
    return {"result": result, "original": untailored(profile)}


@router.get("/html")
def html(job_id: str, profile: MasterProfile = Depends(get_profile), db: Session = Depends(get_db)):
    resume = services.stored_tailoring(db, profile, job_id).resume
    return Response(render.render_html(profile, resume), media_type="text/html")


@router.get("/pdf")
def pdf(job_id: str, profile: MasterProfile = Depends(get_profile), db: Session = Depends(get_db)):
    resume = services.stored_tailoring(db, profile, job_id).resume
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
