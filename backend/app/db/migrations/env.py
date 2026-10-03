from alembic import context
from sqlalchemy import create_engine

from app.core.config import settings
from app.db.models import Base

# tests pass their own URL with -x url=...; everything else uses DATABASE_URL
url = context.get_x_argument(as_dictionary=True).get("url", settings.db_url)

with create_engine(url).connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
