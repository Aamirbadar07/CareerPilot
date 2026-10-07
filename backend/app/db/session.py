from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Fail fast when the database does not answer. Without a connect timeout psycopg waits
# indefinitely, which hangs startup before anything can be logged or served: a paused
# database then looks exactly like a broken image.
_connect_args = {"connect_timeout": 5} if settings.db_url.startswith("postgresql") else {}

engine = create_engine(settings.db_url, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
