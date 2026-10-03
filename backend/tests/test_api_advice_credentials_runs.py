import json

from app import sample
from app.agents.career_coach.prompt import SYSTEM_PROMPT as COACH
from app.agents.resume_analyzer.prompt import SYSTEM_PROMPT as ANALYZER
from app.api.runs import get_sessions
from app.main import app
from conftest import fake_llm, routed_llm

LUMEN = "https://example.com/sample-jobs/lumen-forge-genai-developer"
JOB_ID = next(j["id"] for j in sample.jobs() if j["url"] == LUMEN)
TAILORED = sample.load("tailored.json")[LUMEN]
CREDENTIAL = json.dumps(sample.load("credential.json"))
CERTIFICATE = sample.text("certificate.txt").encode()


def test_demo_data_is_served_read_only(client, db):
    sample.seed(db)
    assert client.get("/api/profiles/sample/linkedin").json()["result"]["headline"][0]
    assert client.get("/api/profiles/sample/coach").json()["plan"]["plan"][0]["rank"] == 1
    body = client.get("/api/profiles/sample").json()
    assert body["is_sample"] and body["expires_at"] is None
    r = client.post("/api/profiles/sample/linkedin", json={"linkedin_text": "x" * 60})
    assert r.status_code == 403


def test_a_new_certificate_changes_the_next_tailored_resume(client, mine):
    """Phase 7's done-when, end to end."""
    tailor_url = f"/api/profiles/{mine}/jobs/{JOB_ID}/tailor"
    assert "AWS Certified AI Practitioner" not in client.get(f"{tailor_url}/html").text

    client.llm = fake_llm(CREDENTIAL)
    files = {"file": ("certificate.txt", CERTIFICATE)}
    proposed = client.post(f"/api/profiles/{mine}/credentials", files=files).json()
    proposal = proposed["proposal"]
    assert proposal["verified"] and proposal["certification"]["id"] == "cert_2"
    assert proposal["downstream"]["stale_resumes"] == [
        "Generative AI Developer (Entry Level) (Lumen Forge AI)"
    ]
    assert proposal["downstream"]["gaps_closed"] == []  # fundamentals do not close "AWS hands-on"

    # nothing is written until the user confirms
    assert client.get(f"/api/profiles/{mine}").json()["profile"]["version"] == 1
    pending = client.get(f"/api/profiles/{mine}/credentials").json()["pending"]
    assert [p["proposal_id"] for p in pending] == [proposed["proposal_id"]]

    confirmed = client.post(f"/api/profiles/{mine}/credentials/{proposed['proposal_id']}/confirm")
    assert confirmed.json()["profile"]["version"] == 2
    history = client.get(f"/api/profiles/{mine}/credentials").json()
    assert history["history"][0]["change"] == "added cert_2" and history["pending"] == []

    # the old tailored resume and coaching plan are gone, and fit reports are stale
    assert client.get(tailor_url).status_code == 404
    assert client.get(f"/api/profiles/{mine}/coach").json()["plan"] is None
    assert client.get(f"/api/profiles/{mine}/jobs").json()["jobs"][0]["fit"] is None

    # the next tailoring run uses the new profile, so the certificate is on the resume
    fit = json.dumps(sample.load("fits.json")[LUMEN])
    client.llm = fake_llm(fit, json.dumps(TAILORED["resume"]), json.dumps(TAILORED["validation"]))
    assert client.post(tailor_url).status_code == 200
    assert (
        "AWS Certified AI Practitioner, Amazon Web Services"
        in client.get(f"{tailor_url}/html").text
    )


def test_confirming_twice_or_rejecting(client, mine):
    client.llm = fake_llm(CREDENTIAL, CREDENTIAL)
    base = f"/api/profiles/{mine}/credentials"
    first = client.post(base, data={"statement": "I hold the AWS Certified AI Practitioner."})
    assert first.json()["proposal"]["verified"] is False
    proposal_id = first.json()["proposal_id"]
    assert client.delete(f"{base}/{proposal_id}").status_code == 204
    assert client.post(f"{base}/{proposal_id}/confirm").status_code == 404
    assert client.post(base).status_code == 422  # no evidence at all


def test_preferences_update_is_a_new_version(client, mine):
    prefs = {"remote_only": False, "locations": ["Bengaluru"], "currency": "INR"}
    r = client.put(f"/api/profiles/{mine}/preferences", json=prefs)
    assert r.status_code == 200 and r.json()["version"] == 2
    assert r.json()["provenance"]["change_log"][-1]["agent"] == "user"


def test_linkedin_and_coach_endpoints(client, mine):
    client.llm = fake_llm(json.dumps(sample.load("linkedin.json")))
    r = client.post(
        f"/api/profiles/{mine}/linkedin", json={"linkedin_text": sample.text("linkedin.txt")}
    )
    assert r.status_code == 200 and r.json()["profile_strength"]["score"] == 23

    client.llm = fake_llm(json.dumps(sample.load("coach.json")))
    r = client.post(f"/api/profiles/{mine}/coach")
    assert r.status_code == 200 and len(r.json()["plan"]) == 5


def test_one_click_run_streams_progress(client, sessions):
    """Phase 8's done-when: upload, and every agent reports over Server-Sent Events."""
    app.dependency_overrides[get_sessions] = lambda: sessions
    client.llm = routed_llm({ANALYZER: json.dumps(sample.load("analysis.json")), COACH: "unused"})
    files = {"file": ("resume.txt", sample.text("resume.txt").encode())}
    run_id = client.post("/api/runs", files=files).json()["run_id"]

    with client.stream("GET", f"/api/runs/{run_id}/stream") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())

    events = [
        json.loads(line[6:]) for line in body.splitlines() if line.startswith('data: {"agent')
    ]
    assert events[0] == {"agent": "resume_analyzer", "status": "started", "detail": ""}
    assert events[1]["status"] == "succeeded" and "ATS score 73" in events[1]["detail"]
    # no job sources are reachable in tests and discovery has no route: it degrades, the run ends
    assert ("job_discovery", "failed") in [(e["agent"], e["status"]) for e in events]
    assert body.rstrip().splitlines()[-2] == "event: done"

    snapshot = client.get(f"/api/runs/{run_id}").json()
    assert snapshot["done"] and snapshot["profile_id"]
    assert client.get(f"/api/profiles/{snapshot['profile_id']}").status_code == 200


def test_run_needs_a_resume_or_an_own_profile(client, db):
    sample.seed(db)
    assert client.post("/api/runs", data={"profile_id": "sample"}).status_code == 403
    assert client.post("/api/runs", data={"profile_id": "nope"}).status_code == 422
    assert client.get("/api/runs/unknown").status_code == 404
