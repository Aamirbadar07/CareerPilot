import json

from app import sample
from app.agents.job_discovery import sources
from app.agents.job_discovery.agent import job_id
from app.agents.job_discovery.schema import RawPosting
from app.db import repositories as repo
from conftest import fake_llm

FIXTURE = sample.load("jobs.json")


def test_sample_jobs_are_seeded_with_fit_reports(client, db):
    sample.seed(db)
    body = client.get("/api/profiles/sample/jobs").json()
    assert len(body["jobs"]) == 6
    first = body["jobs"][0]
    assert first["id"] == job_id(first["url"]) and first["fit"]["band"] == "Strong"
    assert first["tailored"] is True and body["jobs"][1]["tailored"] is False
    assert len(body["discovery"]["queries"]) == 10
    assert client.get(f"/api/profiles/sample/jobs/{first['id']}").json()["fit"]["score"] == 89
    assert client.get("/api/profiles/sample/jobs/nope").status_code == 404


def test_sample_profile_is_read_only(client, db):
    sample.seed(db)
    assert client.post("/api/profiles/sample/jobs/discover").status_code == 403
    assert client.post("/api/profiles/sample/coach").status_code == 403
    assert client.delete("/api/profiles/sample").status_code == 403


def test_discover_stores_jobs(client, mine, monkeypatch):
    job = FIXTURE["jobs"][0] | {"url": "https://example.com/new", "posted": "2099-01-01"}
    fields = {k: job[k] for k in ("url", "title", "company", "description", "posted")}
    monkeypatch.setattr(
        sources, "SOURCES", {"feed": lambda q: [RawPosting(**fields, source="feed")]}
    )
    client.llm = fake_llm(json.dumps({"queries": FIXTURE["queries"]}), json.dumps({"jobs": [job]}))

    r = client.post(f"/api/profiles/{mine}/jobs/discover")
    assert r.status_code == 200, r.text
    assert r.json()["jobs"][0]["source"] == "feed"
    assert len(client.get(f"/api/profiles/{mine}/jobs").json()["jobs"]) == 7


def test_paste_adds_a_job_or_explains_why_not(client, mine):
    job = FIXTURE["jobs"][3]
    text = job["description"]
    client.llm = fake_llm(json.dumps({"jobs": [job | {"url": f"pasted:{job_id(text)}"}]}))
    r = client.post(f"/api/profiles/{mine}/jobs/paste", json={"text": text})
    assert r.status_code == 200 and r.json()["company"] == "Tallyroot"

    dropped = {"dropped": [{"title": "x", "company": "", "reason": "recruiter spam"}]}
    client.llm = fake_llm(json.dumps(dropped))
    r = client.post(f"/api/profiles/{mine}/jobs/paste", json={"text": text + " again"})
    assert r.status_code == 422 and "recruiter spam" in r.json()["detail"]

    assert (
        client.post(f"/api/profiles/{mine}/jobs/paste", json={"text": "short"}).status_code == 422
    )


def test_fit_is_cached_per_profile_version(client, db, mine):
    client.llm = fake_llm()  # every job already has a current report: no model call allowed
    r = client.post(f"/api/profiles/{mine}/jobs/fit", json={})
    assert r.status_code == 200 and len(r.json()["fits"]) == 6 and r.json()["failed"] == []

    profile = sample.profile(mine)  # a new profile version makes every report stale
    profile.version = 2
    repo.save_profile(db, profile)
    assert client.get(f"/api/profiles/{mine}/jobs").json()["jobs"][0]["fit"] is None
