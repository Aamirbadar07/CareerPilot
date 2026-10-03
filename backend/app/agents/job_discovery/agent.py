import hashlib
import re
from datetime import UTC, date, datetime, timedelta

from app.agents.job_discovery.prompt import SYSTEM_PROMPT
from app.agents.job_discovery.schema import Dropped, Job, JobDiscoveryResult, RawPosting
from app.agents.job_discovery.sources import SOURCES, collect
from app.core.llm import LLM
from app.schemas.profile import MasterProfile

# ponytail: one normalise call per run, so the newest 30 relevant postings. Batch the call
# (and dedupe across batches) when recall matters more than cost.
MAX_POSTINGS = 30
MAX_AGE_DAYS = 45
_ABOVE_ENTRY = re.compile(
    r"\b(senior|sr|staff|lead|principal|manager|director|head|vp|architect)\b", re.IGNORECASE
)


def _candidate(profile: MasterProfile) -> dict:
    return {
        "target_roles": [r.model_dump() for r in profile.target_roles],
        "preferences": profile.preferences.model_dump(),
    }


def _key(posting: RawPosting) -> tuple[str, str, str]:
    def norm(s):
        return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

    return norm(posting.company), norm(posting.title), posting.url.split("?")[0].rstrip("/")


def prefilter(
    postings: list[RawPosting], profile: MasterProfile, today: date
) -> tuple[list[RawPosting], list[Dropped]]:
    """The drops that need no judgement, done in code so they cost nothing and cannot be
    argued with: stale, excluded company, exact duplicate, above an entry-level band."""
    cutoff = (today - timedelta(days=MAX_AGE_DAYS)).isoformat()
    excluded = {c.lower() for c in profile.preferences.exclude_companies}
    entry_level = all((r.seniority or "entry") in ("entry", "junior") for r in profile.target_roles)
    kept, dropped, seen = [], [], set()

    for p in postings:
        reason = None
        if p.posted and p.posted < cutoff:
            reason = f"older than {MAX_AGE_DAYS} days"
        elif p.company.lower() in excluded:
            reason = "company excluded in preferences"
        elif entry_level and _ABOVE_ENTRY.search(p.title):
            reason = "above the candidate's seniority band"
        elif _key(p) in seen:
            reason = "duplicate of a posting already kept"
        if reason:
            dropped.append(Dropped(title=p.title, company=p.company, reason=reason))
        else:
            seen.add(_key(p))
            kept.append(p)
    return kept[:MAX_POSTINGS], dropped


def job_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def _salary_supported(salary: str, source: RawPosting) -> bool:
    haystack = f"{source.salary or ''} {source.description}"
    return all(number in haystack for number in re.findall(r"\d+", salary))


def normalise(
    llm: LLM, profile: MasterProfile, raw: list[RawPosting], today: date
) -> JobDiscoveryResult:
    """Phase 2 of the prompt, then the no-invention guard: a job survives only if its URL is
    one we fetched, and the facts a source states are copied from the source, not the model."""
    if not raw:
        return JobDiscoveryResult()
    result = llm.complete(
        SYSTEM_PROMPT,
        {
            "phase": "2 - NORMALISE AND DEDUPE",
            "today": today.isoformat(),
            **_candidate(profile),
            "raw_postings": [p.model_dump() | {"description": p.description[:3000]} for p in raw],
        },
        JobDiscoveryResult,
        profile_id=profile.profile_id,
    )
    by_url = {p.url: p for p in raw}
    jobs: list[Job] = []
    for job in result.jobs:
        source = by_url.get(job.url)
        if source is None:
            result.dropped.append(
                Dropped(
                    title=job.title,
                    company=job.company,
                    reason="rejected: its URL is not in the source data",
                )
            )
            continue
        if source.source != "pasted":  # a pasted description has no structured facts to copy
            job.title, job.company, job.location = source.title, source.company, source.location
            job.posted = source.posted
        job.source = source.source
        job.id = job_id(job.url)
        job.mirrors = [m for m in job.mirrors if m in by_url and m != job.url]
        job.description = source.description
        if job.salary and not _salary_supported(job.salary, source):
            job.salary = None
        jobs.append(job)
    result.jobs = jobs
    return result


def discover_jobs(
    llm: LLM, profile: MasterProfile, today: date | None = None
) -> JobDiscoveryResult:
    today = today or datetime.now(UTC).date()
    plan = llm.complete(
        SYSTEM_PROMPT,
        {"phase": "1 - QUERY EXPANSION", **_candidate(profile), "available_sources": list(SOURCES)},
        JobDiscoveryResult,
        profile_id=profile.profile_id,
    )
    postings, failed_sources = collect(plan.queries)
    raw, dropped = prefilter(postings, profile, today)
    result = normalise(llm, profile, raw, today)
    result.queries = plan.queries
    result.dropped = dropped + result.dropped
    result.dropped += [
        Dropped(title="(source)", company=name, reason="source unavailable this run")
        for name in failed_sources
    ]
    return result


def job_from_text(
    llm: LLM, profile: MasterProfile, text: str, url: str | None = None
) -> JobDiscoveryResult:
    """A job description the user pasted (the only route for sites we must not scrape)."""
    posting = RawPosting(
        url=url or f"pasted:{job_id(text)}", title="", company="", source="pasted", description=text
    )
    return normalise(llm, profile, [posting], datetime.now(UTC).date())
