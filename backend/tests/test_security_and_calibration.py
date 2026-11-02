import json

from app import sample
from app.agents.fit_scorer.agent import score_job
from app.agents.fit_scorer.schema import MULTI_MUST_HAVE_CAP, MUST_HAVE_CAP
from app.agents.job_discovery.schema import Job
from app.core.config import Settings
from conftest import fake_llm

PROFILE = sample.profile()
JOBS = {j["url"]: Job(**j) for j in sample.jobs()}
FITS = sample.load("fits.json")
TALLYROOT = "https://example.com/sample-jobs/tallyroot-python-backend-developer"
PAPERKITE = "https://example.com/sample-jobs/paperkite-associate-llm-developer"


def test_invalid_profile_id_format_is_rejected_with_400(client):
    assert client.get("/api/profiles/../etc/passwd").status_code in (400, 404)
    assert client.get("/api/profiles/bad!@#$id").status_code == 400
    assert client.get(f"/api/profiles/{'a' * 37}").status_code == 400


def test_multi_origin_cors_setting():
    s = Settings(frontend_origin="http://localhost:3000, https://career-pilot-lac.vercel.app")
    assert s.frontend_origins == ["http://localhost:3000", "https://career-pilot-lac.vercel.app"]


def test_single_missing_must_have_caps_at_60():
    # Tallyroot has 1 missing must-have (pytest)
    report = score_job(fake_llm(json.dumps(FITS[TALLYROOT])), PROFILE, JOBS[TALLYROOT])
    assert report.score == MUST_HAVE_CAP
    assert report.band == "Competitive"
    assert report.capped is True


def test_multiple_missing_must_haves_caps_at_54_stretch():
    # If a model inflates dimensions for Paperkite (which misses 2 must-haves: agents & AWS)
    inflated = json.dumps({
        "score": 85,
        "band": "Strong",
        "dimensions": [
            {"name": "must-have skill coverage", "score": 30, "max": 35, "why": "inflated"},
            {"name": "nice-to-have skill coverage", "score": 8, "max": 10, "why": "inflated"},
            {"name": "experience depth vs requirement", "score": 18, "max": 20, "why": "inflated"},
            {"name": "domain and project relevance", "score": 18, "max": 20, "why": "inflated"},
            {"name": "seniority alignment", "score": 8, "max": 10, "why": "inflated"},
            {"name": "location / remote / type fit", "score": 5, "max": 5, "why": "inflated"}
        ],
        "matched": [{"skill": "Python", "evidence": "b_1"}],
        "missing": [
            {"skill": "agents / tool calling", "type": "blocker", "how_to_close": "close gap"},
            {"skill": "AWS", "type": "blocker", "how_to_close": "close gap"}
        ],
        "closable_now": [],
        "resume_angle": "Focus on python",
        "application_priority": 3,
        "verdict": "Candidate misses multiple must-haves.",
        "capped": False
    })
    report = score_job(fake_llm(inflated), PROFILE, JOBS[PAPERKITE])
    # Total dimension sum is 87, but with 2 missing must-haves, cap at 54 (Stretch)
    assert report.score == MULTI_MUST_HAVE_CAP
    assert report.band == "Stretch"
    assert report.capped is True


def test_read_profile_safe_when_profile_row_is_missing(client, db, mine):
    # If the profile version exists but Profile table row is missing
    from app.db.models import Profile
    db.query(Profile).filter(Profile.id == mine).delete()
    db.commit()

    r = client.get(f"/api/profiles/{mine}")
    assert r.status_code == 200
    assert r.json()["expires_at"] is None
