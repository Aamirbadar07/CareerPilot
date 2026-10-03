from datetime import UTC, datetime, timedelta

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from app.db import repositories as repo
from app.db.models import Base


def test_profile_round_trips_and_versions(db, example_profile):
    repo.save_profile(db, example_profile)
    newer = example_profile.model_copy(update={"version": example_profile.version + 1})
    repo.save_profile(db, newer)

    assert repo.get_profile(db, example_profile.profile_id) == newer
    assert repo.get_profile(db, example_profile.profile_id, example_profile.version) == (
        example_profile
    )
    assert repo.get_profile(db, "missing") is None


def test_purge_removes_expired_profiles_and_their_cache(db, sessions, example_profile):
    repo.save_profile(db, example_profile, ttl=timedelta(hours=1))
    sample = example_profile.model_copy(update={"profile_id": "sample"})
    repo.save_profile(db, sample)  # no ttl: never expires
    cache = repo.DbCache(sessions)
    cache.set("k", "v", profile_id=example_profile.profile_id)

    assert repo.purge_expired(db) == 0
    assert repo.purge_expired(db, now=datetime.now(UTC) + timedelta(hours=2)) == 1
    assert repo.get_profile(db, example_profile.profile_id) is None
    assert cache.get("k") is None
    assert repo.get_profile(db, "sample") == sample


def test_migrations_match_models(tmp_path):
    url = f"sqlite:///{tmp_path / 'm.db'}"
    cfg = Config("alembic.ini")
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={url}"]})()
    command.upgrade(cfg, "head")
    with create_engine(url).connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []
