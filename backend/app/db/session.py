from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Fail fast when the database does not answer. Without a connect timeout psycopg waits
# indefinitely, which hangs startup before anything can be logged or served: a paused
# database then looks exactly like a broken image.
# For SQLite, check_same_thread=False allows worker threads (e.g. fit scorer pool) to share
# connection pools safely, and timeout=30 prevents database locked errors.
if settings.db_url.startswith("postgresql"):
    _connect_args = {"connect_timeout": 5}
    _engine_kwargs = {"pool_size": 10, "max_overflow": 20}
else:
    _connect_args = {"check_same_thread": False, "timeout": 30}
    _engine_kwargs = {}

engine = create_engine(
    settings.db_url, pool_pre_ping=True, connect_args=_connect_args, **_engine_kwargs
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
