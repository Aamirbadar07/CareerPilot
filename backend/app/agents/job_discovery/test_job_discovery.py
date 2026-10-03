import copy
import json
from datetime import date

import pytest

from app import sample
from app.agents.job_discovery import sources
from app.agents.job_discovery.agent import discover_jobs, job_from_text, job_id, prefilter
from app.agents.job_discovery.schema import Query, RawPosting
from conftest import fake_llm

FIXTURE = sample.load("jobs.json")
PROFILE = sample.profile()
TODAY = date(2026, 10, 3)
PLAN = json.dumps({"queries": FIXTURE["queries"]})


def raw(job: dict, **overrides) -> RawPosting:
    fields = {k: job.get(k) for k in ("url", "title", "company", "location", "posted", "salary")}
    fields |= {"source": "remotive", "description": job["description"]}
    return RawPosting(**fields | overrides)


@pytest.fixture
def feed(monkeypatch):
    """Replace every source with one in-memory feed built from the sample jobs."""
    first, second = FIXTURE["jobs"][0], FIXTURE["jobs"][1]
    postings = [raw(j) for j in FIXTURE["jobs"]]
    postings.append(raw(second, url=second["mirrors"][0]))
    postings.append(raw(first, title="Senior AI Engineer", url="https://example.com/senior"))
    postings.append(raw(first, posted="2026-07-01", url="https://example.com/old"))
    monkeypatch.setattr(sources, "SOURCES", {"feed": lambda queries: postings})
    return postings


def test_discovery_keeps_source_facts_and_reports_drops(feed):
    llm = fake_llm(PLAN, json.dumps(FIXTURE))
    result = discover_jobs(llm, PROFILE, TODAY)

    assert len(result.queries) == 10
    assert {j.title for j in result.jobs} == {j["title"] for j in FIXTURE["jobs"]}
    assert all(j.id == job_id(j.url) and j.source == "remotive" for j in result.jobs)
    assert result.jobs[1].mirrors == FIXTURE["jobs"][1]["mirrors"]
    reasons = " | ".join(d.reason for d in result.dropped)
    assert "older than 45 days" in reasons and "seniority band" in reasons
    sent = json.loads(llm.calls[1][1][0]["content"])["raw_postings"]
    assert "Senior AI Engineer" not in [p["title"] for p in sent]


def test_invented_job_and_invented_salary_are_removed(feed):
    response = copy.deepcopy(FIXTURE)
    response["jobs"].append(response["jobs"][0] | {"url": "https://example.com/invented"})
    response["jobs"][1]["salary"] = "INR 40 LPA"  # the posting states no salary
    response["jobs"][2]["company"] = "A Better Company"

    result = discover_jobs(fake_llm(PLAN, json.dumps(response)), PROFILE, TODAY)

    assert "https://example.com/invented" not in [j.url for j in result.jobs]
    assert any("not in the source data" in d.reason for d in result.dropped)
    assert result.jobs[1].salary is None
    assert result.jobs[0].salary == "INR 6-9 LPA"
    assert result.jobs[2].company == "Paperkite Software"


def test_one_failing_source_does_not_block_the_others(monkeypatch):
    def boom(queries):
        raise sources.httpx.ConnectError("down")

    good = [raw(FIXTURE["jobs"][0])]
    monkeypatch.setattr(sources, "SOURCES", {"bad": boom, "good": lambda q: good})
    response = json.dumps({"jobs": [FIXTURE["jobs"][0]]})
    result = discover_jobs(fake_llm(PLAN, response), PROFILE, TODAY)
    assert len(result.jobs) == 1
    assert any(d.company == "bad" for d in result.dropped)


def test_relevance_prefers_title_matches():
    queries = [
        Query(q="Junior AI Engineer", source="x"),
        Query(q="Python LangChain remote", source="x"),
    ]
    boilerplate = "We are an AI company. Every engineer here uses Python and LangChain."

    def score(title):
        posting = RawPosting(url="u", title=title, company="c", source="s", description=boilerplate)
        return sources.relevance(queries, posting)

    assert score("AI Engineer") == 2  # the seniority word in the query is optional
    assert score("Software Engineer, AI Platform") == 2
    assert score("Python Developer (LangChain, LLMs)") == 2
    assert score("Account Executive, AI Native") == 0  # one shared word is not enough
    assert score("Account Executive") == 0  # description text never counts


def test_clean_handles_escaped_html():
    assert sources.clean("&lt;p&gt;Build &amp;amp; ship&lt;/p&gt;<b>now</b>") == "Build & ship now"


def test_prefilter_drops_exact_duplicates():
    posting = raw(FIXTURE["jobs"][0])
    kept, dropped = prefilter([posting, posting], PROFILE, TODAY)
    assert len(kept) == 1 and dropped[0].reason.startswith("duplicate")


def test_pasted_job_keeps_the_extracted_title():
    job = FIXTURE["jobs"][3]
    response = json.dumps({"jobs": [job | {"url": f"pasted:{job_id(job['description'])}"}]})
    result = job_from_text(fake_llm(response), PROFILE, job["description"])
    assert result.jobs[0].title == "Python Backend Developer I"
    assert result.jobs[0].source == "pasted"


SOURCE_PAYLOADS = {
    "remotive": {
        "jobs": [
            {
                "url": "https://remotive.com/remote-jobs/x/1",
                "title": "Junior AI Engineer",
                "company_name": "Acme",
                "candidate_required_location": "Worldwide",
                "publication_date": "2026-09-30T13:15:26",
                "salary": "",
                "description": "<p>Python &amp; LLMs</p>",
            }
        ]
    },
    "greenhouse": {
        "jobs": [
            {
                "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/1",
                "title": "LLM Engineer",
                "company_name": "Acme",
                "location": {"name": "Remote, India"},
                "first_published": "2026-10-02T11:31:50-04:00",
                "content": "&lt;p&gt;Build RAG&lt;/p&gt;",
            }
        ]
    },
    "jsearch": {
        "data": [
            {
                "job_apply_link": "https://acme.example/apply/1",
                "job_title": "Generative AI Developer",
                "employer_name": "Acme",
                "job_is_remote": True,
                "job_posted_at_datetime_utc": "2026-10-01T00:00:00.000Z",
                "job_min_salary": 600000,
                "job_max_salary": 900000,
                "job_description": "Build GenAI apps.",
            }
        ]
    },
}


@pytest.mark.parametrize("name", list(SOURCE_PAYLOADS))
def test_source_adapters_map_fields(monkeypatch, name):
    monkeypatch.setattr(sources, "get_json", lambda url, *a, **k: SOURCE_PAYLOADS[name])
    monkeypatch.setattr(sources.settings, "rapidapi_key", "test-key")
    [posting] = getattr(sources, name)([Query(q="Generative AI Developer", source="jsearch")])
    assert posting.company == "Acme" and posting.posted.startswith("2026-")
    assert "<" not in posting.description and posting.description
