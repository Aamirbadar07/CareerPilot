import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.llm import LLM, LLMError
from app.db.models import Base
from app.schemas.profile import MasterProfile

EXAMPLE = Path(__file__).parent / "app" / "schemas" / "profile_schema.json"


def fake_llm(*responses: str) -> LLM:
    """An LLM that replays fixture responses in order through the real parse/validate/retry
    path, with no network. llm.calls records (system, messages) per call."""
    llm = LLM()
    queue = list(responses)
    llm.calls = []

    def raw(system, messages):
        llm.calls.append((system, [dict(m) for m in messages]))
        return queue.pop(0)

    llm._raw = raw
    return llm


def routed_llm(routes: dict) -> LLM:
    """An LLM that answers by system prompt instead of by call order, for code that calls
    agents from several threads. A route is a JSON string or a function of the parsed input.
    A prompt with no route fails the way an unreachable model does."""
    llm = LLM()
    llm.calls = []

    def raw(system, messages):
        llm.calls.append((system, [dict(m) for m in messages]))
        if system not in routes:
            raise LLMError("no route for this prompt")
        route = routes[system]
        return route(json.loads(messages[0]["content"])) if callable(route) else route

    llm._raw = raw
    return llm


@pytest.fixture
def example_profile() -> MasterProfile:
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["certifications"][0]["source"] = (
        "upload"  # the file writes the enum as "upload|link|manual"
    )
    return MasterProfile.model_validate(data)


@pytest.fixture
def sessions():
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def db(sessions):
    with sessions() as session:
        yield session


@pytest.fixture
def client(sessions):
    """API client on the in-memory database. Tests set client.llm to a fake_llm(...)."""
    from fastapi.testclient import TestClient

    from app.api.deps import get_llm
    from app.db.session import get_db
    from app.main import app

    def db():
        with sessions() as session:
            yield session

    client = TestClient(app)  # not used as a context manager, so lifespan seeding is skipped
    client.llm = None
    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_llm] = lambda: client.llm
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def mine(db) -> str:
    """A profile the tests may change: the sample data under an id that is not read-only."""
    from datetime import timedelta

    from app import sample

    sample.seed(db, "mine", ttl=timedelta(hours=24))
    return "mine"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """CLAUDE.md rule 8: a test that reaches a job source fails instead of going online."""
    from app.agents.job_discovery import sources

    def blocked(url, *args, **kwargs):
        raise AssertionError(f"test tried to fetch {url}")

    monkeypatch.setattr(sources, "get_json", blocked)
    # Tests must not depend on, or spend, whatever is in the developer's .env.
    from app.core.config import settings

    for name, value in (
        ("llm_provider", "anthropic"),
        ("anthropic_api_key", ""),
        ("google_api_key", ""),
    ):
        monkeypatch.setattr(settings, name, value)
