"""/health is the only thing that can explain an outage from outside, so it has to answer
even when the database does not."""

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db.session import get_db
from app.main import app


def _refused(*_args, **_kwargs):
    raise OperationalError("select 1", {}, Exception("connection refused"))


class DeadSession:
    """A session whose first query fails, the way an unreachable database behaves."""

    execute = _refused


def test_health_reports_a_working_database(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


def test_health_is_200_but_degraded_when_the_database_is_down(client):
    app.dependency_overrides[get_db] = DeadSession
    r = client.get("/health")
    # 200 on purpose: Cloud Run and Render restart a container whose health check fails,
    # and a restart cannot fix a database outage. The body carries the verdict.
    assert r.status_code == 200
    assert r.json()["status"] == "degraded"
    assert "OperationalError" in r.json()["database"]


def test_the_app_starts_even_when_the_database_is_unreachable(monkeypatch, client):
    """Seeding the demo data used to run before the app could serve anything, so a database
    outage left no logs, no /health and a blank 500."""
    monkeypatch.setattr("app.main.SessionLocal", _refused)
    app.dependency_overrides[get_db] = DeadSession
    with TestClient(app) as started:  # entering the client runs the lifespan
        r = started.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "degraded"
