import json

from app import sample
from app.db import repositories as repo
from conftest import fake_llm

RESUME = sample.text("resume.txt").encode()
RESPONSE = json.dumps(sample.load("analysis.json"))


def test_upload_read_delete(client, db):
    client.llm = fake_llm(RESPONSE)
    r = client.post("/api/resume", files={"file": ("my resume.txt", RESUME)})
    assert r.status_code == 200, r.text
    body = r.json()
    profile_id = body["profile"]["profile_id"]
    assert body["analysis"]["ats"]["score"] == 73

    r = client.get(f"/api/profiles/{profile_id}")
    assert r.json()["profile"]["identity"]["full_name"] == "Asha Verma"
    assert r.json()["analysis"]["weak_bullets"][0]["bullet_id"] == "b_2"

    assert client.delete(f"/api/profiles/{profile_id}").status_code == 204
    assert client.get(f"/api/profiles/{profile_id}").status_code == 404
    assert repo.get_artifact(db, profile_id, "resume_analysis") is None


def test_bad_uploads_never_reach_the_model(client):
    client.llm = fake_llm()  # any model call would raise IndexError
    assert client.post("/api/resume", files={"file": ("a.exe", b"x" * 500)}).status_code == 422
    big = client.post("/api/resume", files={"file": ("a.txt", b"x" * (5 * 1024 * 1024 + 1))})
    assert big.status_code == 422


def test_sample_profile_is_seeded_and_protected(client, db):
    sample.seed(db)
    sample.seed(db)  # idempotent
    assert client.get("/api/profiles/sample").json()["profile"]["version"] == 1
    assert client.delete("/api/profiles/sample").status_code == 403


def test_model_failure_is_a_502_not_a_crash(client):
    client.llm = fake_llm("not json", "still not json")
    r = client.post("/api/resume", files={"file": ("r.txt", RESUME)})
    assert r.status_code == 502
