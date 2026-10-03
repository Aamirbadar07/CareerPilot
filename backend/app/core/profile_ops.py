"""Changes to the master profile. Every change is a new version with a change_log entry, so
it can be traced to an agent and reversed (CLAUDE.md rule 2)."""

from datetime import UTC, datetime

from app.agents.credentials.schema import CredentialProposal
from app.core.guard import norm
from app.schemas.profile import ChangeLogEntry, MasterProfile, Skill


def bump(profile: MasterProfile, agent: str, change: str) -> MasterProfile:
    """Stamp an edited copy as the next version. Only called after the user approved."""
    now = datetime.now(UTC).isoformat()
    profile.version += 1
    profile.updated_at = now
    profile.provenance.change_log.append(
        ChangeLogEntry(
            version=profile.version, agent=agent, change=change, at=now, approved_by_user=True
        )
    )
    return profile


def apply_credential(profile: MasterProfile, proposal: CredentialProposal) -> MasterProfile:
    """The approved certification, and the skills it certifies, as a new profile version."""
    new = profile.model_copy(deep=True)
    cert = proposal.certification
    updating = proposal.profile_patch.op == "update"
    if updating:
        new.certifications = [cert if c.id == cert.id else c for c in new.certifications]
    else:
        new.certifications.append(cert)

    by_name = {norm(s.name): s for s in new.skills}
    for name in proposal.skills_covered:
        if skill := by_name.get(norm(name)):
            if cert.id not in skill.evidence:
                skill.evidence.append(cert.id)
        else:
            new.skills.append(
                Skill(
                    name=name,
                    category="certified",
                    evidence=[cert.id],
                    first_seen=cert.issued,
                    verified=cert.verified,
                )
            )
    return bump(new, "credentials", f"{'updated' if updating else 'added'} {cert.id}")
