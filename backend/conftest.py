import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.llm import LLM
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


@pytest.fixture
def example_profile() -> MasterProfile:
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["certifications"][0]["source"] = "upload"  # the file writes the enum as "upload|link|manual"
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
