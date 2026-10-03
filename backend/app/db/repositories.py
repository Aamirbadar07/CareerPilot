from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Artifact, LLMCache, Profile, ProfileVersion
from app.schemas.profile import MasterProfile


def save_profile(db: Session, profile: MasterProfile, ttl: timedelta | None = None) -> None:
    """Store profile.version as a new immutable row. ttl applies only when the profile is new;
    ttl=None on a new profile means it never expires (the sample profile)."""
    if db.get(Profile, profile.profile_id) is None:
        expires = datetime.now(UTC) + ttl if ttl else None
        db.add(Profile(id=profile.profile_id, expires_at=expires))
    db.add(
        ProfileVersion(
            profile_id=profile.profile_id, version=profile.version, data=profile.model_dump()
        )
    )
    db.commit()


def get_profile(db: Session, profile_id: str, version: int | None = None) -> MasterProfile | None:
    """Latest version unless one is named."""
    q = select(ProfileVersion).where(ProfileVersion.profile_id == profile_id)
    if version is not None:
        q = q.where(ProfileVersion.version == version)
    row = db.scalars(q.order_by(ProfileVersion.version.desc()).limit(1)).first()
    return MasterProfile.model_validate(row.data) if row else None


def delete_profile(db: Session, profile_id: str) -> None:
    """Delete a profile and everything derived from it."""
    db.execute(delete(LLMCache).where(LLMCache.profile_id == profile_id))
    db.execute(delete(Artifact).where(Artifact.profile_id == profile_id))
    db.execute(delete(ProfileVersion).where(ProfileVersion.profile_id == profile_id))
    db.execute(delete(Profile).where(Profile.id == profile_id))
    db.commit()


def purge_expired(db: Session, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    ids = db.scalars(select(Profile.id).where(Profile.expires_at < now)).all()
    for profile_id in ids:
        delete_profile(db, profile_id)
    return len(ids)


def put_artifact(
    db: Session, profile_id: str, kind: str, data: dict, profile_version: int, ref: str = ""
) -> None:
    """Insert or replace the artifact for (profile, kind, ref)."""
    db.execute(
        delete(Artifact).where(
            Artifact.profile_id == profile_id, Artifact.kind == kind, Artifact.ref == ref
        )
    )
    db.add(
        Artifact(
            profile_id=profile_id, kind=kind, ref=ref, profile_version=profile_version, data=data
        )
    )
    db.commit()


def get_artifact(db: Session, profile_id: str, kind: str, ref: str = "") -> Artifact | None:
    return db.scalars(
        select(Artifact).where(
            Artifact.profile_id == profile_id, Artifact.kind == kind, Artifact.ref == ref
        )
    ).first()


def list_artifacts(db: Session, profile_id: str, kind: str) -> list[Artifact]:
    return list(
        db.scalars(
            select(Artifact)
            .where(Artifact.profile_id == profile_id, Artifact.kind == kind)
            .order_by(Artifact.id)
        )
    )


def delete_artifacts(db: Session, profile_id: str, *kinds: str) -> None:
    db.execute(delete(Artifact).where(Artifact.profile_id == profile_id, Artifact.kind.in_(kinds)))
    db.commit()


class DbCache:
    """LLM response cache backed by llm_cache. Opens a short session per call so it is safe
    to share across the fit scorer's worker threads."""

    def __init__(self, session_factory):
        self._sessions = session_factory

    def get(self, key: str) -> str | None:
        with self._sessions() as db:
            row = db.get(LLMCache, key)
            return row.value if row else None

    def set(self, key: str, value: str, profile_id: str | None = None) -> None:
        with self._sessions() as db:
            db.merge(LLMCache(key=key, value=value, profile_id=profile_id))
            db.commit()
