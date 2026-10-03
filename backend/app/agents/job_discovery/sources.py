"""Licensed job sources only (CLAUDE.md rule 4, docs/architecture.md). Each source returns
RawPosting objects; nothing here is scraped."""

import html
import logging
import re
import time
from collections.abc import Callable

import httpx2 as httpx

from app.agents.job_discovery.schema import Query, RawPosting
from app.core.config import settings

log = logging.getLogger("careerpilot.jobs")

# Remotive asks API users to fetch at most about four times a day.
_TTL_SECONDS = 6 * 3600
_cache: dict[str, tuple[float, object]] = {}
_STOPWORDS = {"remote", "job", "jobs", "the", "and", "in", "for", "a", "of"}
_SENIORITY = {"entry", "level", "junior", "associate", "graduate", "intern", "i", "ii"}


def get_json(url: str, params: dict | None = None, headers: dict | None = None):
    key = url + repr(sorted((params or {}).items()))
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < _TTL_SECONDS:
        return hit[1]
    response = httpx.get(url, params=params, headers=headers, timeout=30, follow_redirects=True)
    response.raise_for_status()
    data = response.json()
    _cache[key] = (time.monotonic(), data)
    return data


def clean(text: str | None) -> str:
    """HTML (possibly entity-escaped, as Greenhouse sends it) to plain text."""
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _tokens(text: str) -> set[str]:
    # "node.js" and "c++" stay whole; a sentence-ending dot does not stick to the word
    return set(re.findall(r"[a-z0-9+#]+(?:\.[a-z0-9]+)*", text.lower()))


def relevance(queries: list[Query], posting: RawPosting) -> int:
    """How well the posting's TITLE matches the best query: 2 = every core word, 1 = at least
    two of them, 0 = irrelevant. Descriptions are not searched: company boilerplate mentions
    "AI" and "engineer" in every sales posting. Seniority words are optional, so the query
    "Junior AI Engineer" finds a posting titled "AI Engineer"."""
    title = _tokens(posting.title)
    best = 0
    for query in queries:
        words = _tokens(query.q) - _STOPWORDS - _SENIORITY
        if not words:
            continue
        if words <= title:
            return 2
        if len(words & title) >= 2:
            best = 1
    return best


def remotive(queries: list[Query]) -> list[RawPosting]:
    data = get_json("https://remotive.com/api/remote-jobs")
    return [
        RawPosting(
            url=j["url"],
            title=j["title"],
            company=j["company_name"],
            location=j.get("candidate_required_location") or "Remote",
            posted=(j.get("publication_date") or "")[:10] or None,
            source="remotive",
            salary=j.get("salary") or None,
            description=clean(j.get("description")),
        )
        for j in data.get("jobs", [])
    ]


def greenhouse(queries: list[Query]) -> list[RawPosting]:
    postings = []
    for board in filter(None, (b.strip() for b in settings.greenhouse_boards.split(","))):
        data = get_json(
            f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", {"content": "true"}
        )
        postings += [
            RawPosting(
                url=j["absolute_url"],
                title=j["title"],
                company=j.get("company_name") or board,
                location=(j.get("location") or {}).get("name"),
                posted=(j.get("first_published") or j.get("updated_at") or "")[:10] or None,
                source=f"greenhouse:{board}",
                description=clean(j.get("content")),
            )
            for j in data.get("jobs", [])
        ]
    return postings


def jsearch(queries: list[Query]) -> list[RawPosting]:
    """Google for Jobs via RapidAPI. A search API with a monthly quota, so only the queries
    the planner tagged for it are sent, and at most five per run."""
    if not settings.rapidapi_key:
        return []
    headers = {"X-RapidAPI-Key": settings.rapidapi_key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"}
    postings = []
    for query in [q for q in queries if "jsearch" in q.source.lower()][:5]:
        data = get_json(
            "https://jsearch.p.rapidapi.com/search",
            {"query": query.q, "page": "1", "num_pages": "1", "date_posted": "month"},
            headers,
        )
        for j in data.get("data", []):
            place = ", ".join(filter(None, (j.get("job_city"), j.get("job_country"))))
            pay = [j.get("job_min_salary"), j.get("job_max_salary")]
            postings.append(
                RawPosting(
                    url=j["job_apply_link"],
                    title=j["job_title"],
                    company=j.get("employer_name") or "",
                    location=("Remote" if j.get("job_is_remote") else place) or None,
                    posted=(j.get("job_posted_at_datetime_utc") or "")[:10] or None,
                    source="jsearch",
                    salary=" - ".join(str(p) for p in pay if p) or None,
                    description=clean(j.get("job_description")),
                )
            )
    return postings


SOURCES: dict[str, Callable[[list[Query]], list[RawPosting]]] = {
    "remotive": remotive,
    "greenhouse": greenhouse,
    "jsearch": jsearch,
}


def collect(queries: list[Query]) -> tuple[list[RawPosting], list[str]]:
    """Every relevant posting from every source, best match and newest first. A source that
    fails is reported and skipped; it never blocks the others."""
    postings, failed = [], []
    for name, fetch in SOURCES.items():
        try:
            postings += fetch(queries)
        except (httpx.HTTPError, ValueError, KeyError) as e:
            log.warning("source %s failed: %s", name, type(e).__name__)
            failed.append(name)
    scored = [(relevance(queries, p), p) for p in postings]
    scored = [(score, p) for score, p in scored if score]
    scored.sort(key=lambda sp: (sp[0], sp[1].posted or ""), reverse=True)
    return [p for _, p in scored], failed
