"""artifacts"""

import sqlalchemy as sa
from alembic import op

from app.db.models import Json

revision = "0002"
down_revision = "0001"


def upgrade() -> None:
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("ref", sa.String(64), nullable=False),
        sa.Column("profile_version", sa.Integer, nullable=False),
        sa.Column("data", Json, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("profile_id", "kind", "ref"),
    )
    op.create_index("ix_artifacts_profile_id", "artifacts", ["profile_id"])


def downgrade() -> None:
    op.drop_table("artifacts")
