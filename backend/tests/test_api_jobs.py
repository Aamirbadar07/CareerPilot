import json

from app import sample
from app.agents.job_discovery import sources
from app.agents.job_discovery.agent import job_id
from app.agents.job_discovery.schema import RawPosting
from conftest import fake_llm

FIXTURE = sample.load("jobs.json")


def test_sample_jobs_are_seeded(client, db):
    sample.seed(db)
    body = client.get("/api/profiles/sample/jobs").json()
    assert len(body["jobs"]) == 6
    assert body["jobs"][0]["id"] == job_id(body["jobs"][0]["url"])
    assert len(body["discovery"]["queries"]) == 10


def test_discover_stores_jobs(client, db, monkeypatch):
    sample.seed(db)
    job = FIXTURE["jobs"][0] | {"url": "https://example.com/new", "posted": "2099-01-01"}
    fields = {k: job[k] for k in ("url", "title", "company", "description", "posted")}
    monkeypatch.setattr(
        sources, "SOURCES", {"feed": lambda q: [RawPosting(**fields, source="feed")]}
    )
    client.llm = fake_llm(json.dumps({"queries": FIXTURE["queries"]}), json.dumps({"jobs": [job]}))

    r = client.post("/api/profiles/sample/jobs/discover")
    assert r.status_code == 200, r.text
    assert r.json()["jobs"][0]["source"] == "feed"
    assert len(client.get("/api/profiles/sample/jobs").json()["jobs"]) == 7


def test_paste_adds_a_job_or_explains_why_not(client, db):
    sample.seed(db)
    job = FIXTURE["jobs"][3]
    text = job["description"]
    client.llm = fake_llm(json.dumps({"jobs": [job | {"url": f"pasted:{job_id(text)}"}]}))
    r = client.post("/api/profiles/sample/jobs/paste", json={"text": text})
    assert r.status_code == 200 and r.json()["company"] == "Tallyroot"

    dropped = {"dropped": [{"title": "x", "company": "", "reason": "recruiter spam"}]}
    client.llm = fake_llm(json.dumps(dropped))
    r = client.post("/api/profiles/sample/jobs/paste", json={"text": text + " again"})
    assert r.status_code == 422 and "recruiter spam" in r.json()["detail"]

    assert client.post("/api/profiles/sample/jobs/paste", json={"text": "short"}).status_code == 422


def test_fit_is_cached_per_profile_version(client, db):
    sample.seed(db)
    listed = client.get("/api/profiles/sample/jobs").json()["jobs"]
    assert listed[0]["fit"]["band"] == "Strong"  # seeded

    client.llm = fake_llm()  # every job already has a current report: no model call allowed
    r = client.post("/api/profiles/sample/jobs/fit", json={})
    assert r.status_code == 200 and len(r.json()["fits"]) == 6 and r.json()["failed"] == []

    # a new profile version makes every report stale
    from app.db import repositories as repo

    profile = sample.profile()
    profile.version = 2
    repo.save_profile(db, profile)
    assert client.get("/api/profiles/sample/jobs").json()["jobs"][0]["fit"] is None
