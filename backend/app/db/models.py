from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

Json = JSON().with_variant(JSONB(), "postgresql")


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Profile(Base):
    """One candidate. expires_at NULL = the built-in sample profile, which is never purged."""

    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class ProfileVersion(Base):
    """Immutable snapshot of the master profile JSON. A change is a new row, so it is reversible."""

    __tablename__ = "profile_versions"

    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id"), primary_key=True)
    version: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[dict] = mapped_column(Json)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LLMCache(Base):
    """LLM responses keyed by content hash (CLAUDE.md rule 9). Rows carry the profile they
    were computed for so deleting a profile also deletes what was derived from it."""

    __tablename__ = "llm_cache"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    profile_id: Mapped[str | None] = mapped_column(String(36), index=True)
    value: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
