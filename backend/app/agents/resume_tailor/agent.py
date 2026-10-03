import json
import re
from datetime import UTC, datetime

from app.agents.fit_scorer.agent import profile_for_llm
from app.agents.fit_scorer.schema import FitReport
from app.agents.job_discovery.schema import Job
from app.agents.resume_tailor.prompt import TAILOR_PROMPT, VALIDATOR_PROMPT
from app.agents.resume_tailor.schema import (
    SkillGroup,
    TailoredBullet,
    TailoredExperience,
    TailoredProject,
    TailoredResume,
    TailorResult,
    ValidationReport,
)
from app.core.llm import LLM, LLMError
from app.schemas.profile import MasterProfile


def _numbers(text: str) -> set[str]:
    """Every number in the text, thousands separators removed: "1,200" -> "1200"."""
    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9+#.]+", text.lower()))


def experience_months(profile: MasterProfile, today: datetime | None = None) -> int:
    today = today or datetime.now(UTC)
    total = 0
    for exp in profile.experience:
        end = exp.end if exp.end and not exp.current else today.strftime("%Y-%m")
        try:
            (y1, m1), (y2, m2) = (map(int, d.split("-")[:2]) for d in (exp.start, end))
        except (AttributeError, ValueError):
            continue  # a role without parseable dates adds nothing
        total += max(0, (y2 - y1) * 12 + (m2 - m1) + 1)
    return total


def _length_phrase(months: int) -> str:
    years, rest = divmod(months, 12)
    parts = []
    if years:
        parts.append(f"{years} year" + ("s" if years != 1 else ""))
    if rest:
        parts.append(f"{rest} month" + ("s" if rest != 1 else ""))
    return " ".join(parts) or "no professional experience"


def fabrications(profile: MasterProfile, resume: TailoredResume) -> list[str]:
    """Deterministic half of the no-fabrication guard: what code can prove without a model.
    Returns problems that name positions, never resume content."""
    problems = []
    exp_ids = {e.id for e in profile.experience}
    proj_ids = {p.id for p in profile.projects}
    bullet_ids = {b.id for e in profile.experience for b in e.bullets}
    bullet_ids |= {b.id for p in profile.projects for b in p.bullets}

    known = [s.name for s in profile.skills]
    known += [t for e in profile.experience for t in e.tech]
    known += [t for p in profile.projects for t in p.tech]
    known += [s for c in profile.certifications for s in c.skills_covered]
    known = {_norm(k) for k in known if k}

    allowed = _numbers(json.dumps(profile.model_dump(exclude={"provenance"})))
    months = experience_months(profile)
    allowed |= _numbers(_length_phrase(months)) | {str(months)}

    texts = {"title_line": resume.title_line, "summary": resume.summary}
    for i, exp in enumerate(resume.experience):
        if exp.exp_id not in exp_ids:
            problems.append(f"experience[{i}].exp_id is not in the profile")
        for j, b in enumerate(exp.bullets):
            texts[f"experience[{i}].bullets[{j}]"] = b.text
            if b.from_bullet not in bullet_ids:
                problems.append(f"experience[{i}].bullets[{j}].from_bullet is not in the profile")
    for i, proj in enumerate(resume.projects):
        if proj.proj_id not in proj_ids:
            problems.append(f"projects[{i}].proj_id is not in the profile")
        for j, b in enumerate(proj.bullets):
            texts[f"projects[{i}].bullets[{j}]"] = b.text
            if b.from_bullet not in bullet_ids:
                problems.append(f"projects[{i}].bullets[{j}].from_bullet is not in the profile")

    for i, group in enumerate(resume.skills):
        for j, item in enumerate(group.items):
            padded = f" {_norm(item)} "
            if not any(f" {skill} " in padded for skill in known):
                problems.append(f"skills[{i}].items[{j}] names no skill that is in the profile")

    for where, text in texts.items():
        if _numbers(text) - allowed:
            problems.append(f"{where} contains a number that is not in the profile")
        if re.search(r"\b(familiar with|exposure to)\b", text, re.IGNORECASE):
            problems.append(f"{where} softens a claim with 'familiar with' or 'exposure to'")
    return problems


def untailored(profile: MasterProfile) -> TailoredResume:
    """The master profile as resume content, word for word. The fallback when tailoring
    cannot be made to pass validation."""
    groups: dict[str, list[str]] = {}
    for skill in profile.skills:
        groups.setdefault(skill.category.title(), []).append(skill.name)

    def bullets(items):
        return [TailoredBullet(text=b.text, from_bullet=b.id) for b in items]

    return TailoredResume(
        title_line=profile.identity.title_line or "",
        summary=profile.summary_source or "",
        skills=[SkillGroup(category=c, items=items) for c, items in groups.items()],
        experience=[
            TailoredExperience(exp_id=e.id, bullets=bullets(e.bullets)) for e in profile.experience
        ],
        projects=[
            TailoredProject(proj_id=p.id, bullets=bullets(p.bullets)) for p in profile.projects
        ],
    )


def _write(llm: LLM, profile: MasterProfile, job: Job, fit: FitReport, feedback: dict):
    def check(resume: TailoredResume) -> None:
        if problems := fabrications(profile, resume):
            raise ValueError("; ".join(problems[:8]))

    return llm.complete(
        TAILOR_PROMPT,
        {
            "master_profile": profile_for_llm(profile),
            "job": job.model_dump(exclude={"mirrors"}) | {"description": job.description[:3000]},
            "fit_report": fit.model_dump(),
            "experience_length": _length_phrase(experience_months(profile)),
            **feedback,
        },
        TailoredResume,
        profile_id=profile.profile_id,
        check=check,
    )


def validate(llm: LLM, profile: MasterProfile, resume: TailoredResume) -> ValidationReport:
    report = llm.complete(
        VALIDATOR_PROMPT,
        {"master_profile": profile_for_llm(profile), "tailored_resume": resume.model_dump()},
        ValidationReport,
        profile_id=profile.profile_id,
    )
    # The verdict follows from the findings; it is not the model's to choose.
    report.must_fix_count = sum(f.must_fix for f in report.findings)
    report.verdict = "fail" if report.must_fix_count else "pass"
    return report


def tailor_resume(
    llm: LLM, profile: MasterProfile, job: Job, fit: FitReport, feedback: dict | None = None
) -> TailorResult:
    """Write, then have a separate call try to break it. One rewrite on failure; after a
    second failure the user gets their untailored resume and the reason."""
    feedback = dict(feedback or {})
    report = None
    for attempt in (1, 2):
        try:
            resume = _write(llm, profile, job, fit, feedback)
            report = validate(llm, profile, resume)
        except LLMError as e:
            return TailorResult(
                status="untailored",
                resume=untailored(profile),
                validation=report,
                attempts=attempt,
                reason=f"Tailoring could not be completed safely ({e}). "
                "This is your resume as written.",
            )
        if report.verdict == "pass":
            return TailorResult(
                status="tailored", resume=resume, validation=report, attempts=attempt
            )
        feedback["validator_findings"] = [f.model_dump() for f in report.findings if f.must_fix]
    return TailorResult(
        status="untailored",
        resume=untailored(profile),
        validation=report,
        attempts=2,
        reason=f"The fact-checker still found {report.must_fix_count} unsupported or overstated "
        "claim(s) after one rewrite, so nothing was changed. This is your resume as written.",
    )
