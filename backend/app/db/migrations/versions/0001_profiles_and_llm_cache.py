"""profiles, profile_versions, llm_cache"""

import sqlalchemy as sa
from alembic import op

from app.db.models import Json

revision = "0001"
down_revision = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_profiles_expires_at", "profiles", ["expires_at"])
    op.create_table(
        "profile_versions",
        sa.Column("profile_id", sa.String(36), sa.ForeignKey("profiles.id"), primary_key=True),
        sa.Column("version", sa.Integer, primary_key=True),
        sa.Column("data", Json, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "llm_cache",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("profile_id", sa.String(36), nullable=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_llm_cache_profile_id", "llm_cache", ["profile_id"])


def downgrade() -> None:
    op.drop_table("llm_cache")
    op.drop_table("profile_versions")
    op.drop_table("profiles")
