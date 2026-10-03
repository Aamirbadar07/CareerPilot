"""Resume rendering. The model returns content JSON; this module owns every layout decision,
so typography, spacing and the one-page limit are identical on every run."""

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.agents.resume_tailor.schema import TailoredResume
from app.schemas.profile import MasterProfile

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parents[1] / "templates"),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


class PdfUnavailable(RuntimeError):
    """WeasyPrint's native libraries (Pango) are not installed on this machine."""


def _month(value: str | None) -> str:
    """'2026-02' -> 'Feb 2026'. Anything else is returned as written."""
    try:
        # a month label only; no instant in time is involved, so no timezone
        return datetime.strptime(value or "", "%Y-%m").strftime("%b %Y")  # noqa: DTZ007
    except ValueError:
        return value or ""


def _span(start: str | None, end: str | None, current: bool = False) -> str:
    parts = [_month(start), "Present" if current else _month(end)]
    return " - ".join(p for p in parts if p)


def render_html(profile: MasterProfile, resume: TailoredResume) -> str:
    """Join the tailored content with the profile's facts (employers, dates, education).
    Those facts are read from the profile here, so the model never gets to restate them."""
    by_id = {e.id: e for e in profile.experience}
    experience = []
    for item in resume.experience:
        if exp := by_id.get(item.exp_id):
            experience.append(
                {
                    "role": exp.role,
                    "company": exp.company,
                    "place": "Remote" if exp.remote else exp.location,
                    "dates": _span(exp.start, exp.end, exp.current),
                    "tech": exp.tech,
                    "bullets": [b.text for b in item.bullets],
                }
            )
    by_id = {p.id: p for p in profile.projects}
    projects = []
    for item in resume.projects:
        if proj := by_id.get(item.proj_id):
            projects.append(
                {
                    "name": proj.name,
                    "one_liner": proj.one_liner or "",
                    "dates": _month(proj.date),
                    "tech": proj.tech,
                    "bullets": [b.text for b in item.bullets],
                }
            )
    identity = profile.identity
    return _env.get_template("resume.html").render(
        identity=identity,
        resume=resume.model_dump(),
        contact=[
            c
            for c in (
                identity.location,
                identity.email,
                identity.phone,
                identity.linkedin,
                identity.github,
                identity.portfolio,
            )
            if c
        ],
        experience=experience,
        projects=projects,
        education=[
            {
                "title": ", ".join(x for x in (e.degree, e.field) if x),
                "institution": e.institution or "",
                "dates": _span(e.start, e.end),
                "score": " ".join(x for x in (e.score_type, e.score) if x) if e.score else "",
            }
            for e in profile.education
        ],
        certifications=[
            {
                "name": c.name,
                "issuer": c.issuer,
                "dates": _month(c.issued),
            }
            for c in profile.certifications
        ],
    )


def page_count(html: str) -> int:
    return len(_weasyprint().HTML(string=html).render().pages)


def render_pdf(html: str) -> bytes:
    return _weasyprint().HTML(string=html).write_pdf()


def fit_to_one_page(profile: MasterProfile, resume: TailoredResume) -> tuple[TailoredResume, str]:
    """Cut from the end until the resume fits one page. Projects go first because the tailor
    orders them by relevance, so the last one is the least relevant; then trailing bullets.
    Cutting can never add a claim, so no re-validation is needed."""
    resume = resume.model_copy(deep=True)
    while page_count(html := render_html(profile, resume)) > 1:
        if len(resume.projects) > 1:
            resume.projects.pop()
        elif resume.projects and len(resume.projects[-1].bullets) > 1:
            resume.projects[-1].bullets.pop()
        elif resume.experience and len(resume.experience[-1].bullets) > 1:
            resume.experience[-1].bullets.pop()
        else:
            break  # nothing left that is safe to cut
    return resume, html


def _weasyprint():
    try:
        import weasyprint
    except OSError as e:  # raised at import when Pango/GObject cannot be loaded
        raise PdfUnavailable(str(e).splitlines()[0]) from None
    return weasyprint
