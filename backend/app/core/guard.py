"""The deterministic half of the no-fabrication rule (CLAUDE.md rule 1): the checks code can
make without a model. Shared by every agent that writes about the candidate. Problems name
positions, never content, because they are fed back to the model and may reach logs."""

import json
import re
from datetime import UTC, datetime

from app.schemas.profile import MasterProfile


def numbers(text: str) -> set[str]:
    """Every number in the text, thousands separators removed: "1,200" -> "1200"."""
    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


def norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9+#]+(?:\.[a-z0-9]+)*", text.lower()))


def experience_months(profile: MasterProfile, today: datetime | None = None) -> int:
    today = today or datetime.now(UTC)
    total = 0
    for exp in profile.experience:
        end = exp.end if exp.end and not exp.current else today.strftime("%Y-%m")
        try:
            (y1, m1), (y2, m2) = (map(int, d.split("-")[:2]) for d in (exp.start, end))
        except (AttributeError, ValueError):
            continue  # a role without parseable dates adds nothing
        total += max(0, (y2 - y1) * 12 + (m2 - m1) + 1)
    return total


def length_phrase(months: int) -> str:
    years, rest = divmod(months, 12)
    parts = []
    if years:
        parts.append(f"{years} year" + ("s" if years != 1 else ""))
    if rest:
        parts.append(f"{rest} month" + ("s" if rest != 1 else ""))
    return " ".join(parts) or "no professional experience"


def known_skills(profile: MasterProfile) -> set[str]:
    known = [s.name for s in profile.skills]
    known += [t for e in profile.experience for t in e.tech]
    known += [t for p in profile.projects for t in p.tech]
    known += [s for c in profile.certifications for s in c.skills_covered]
    return {norm(k) for k in known if k}


def names_known_skill(item: str, known: set[str]) -> bool:
    """True if the item contains a profile skill as whole words, so the job's wording is
    allowed around it: "pgvector (vector database)" passes, "Kubernetes" does not."""
    padded = f" {norm(item)} "
    return any(f" {skill} " in padded for skill in known)


def allowed_numbers(profile: MasterProfile) -> set[str]:
    """Numbers a rewrite may use: those already in the profile, plus the experience length,
    which code computes and hands to the model."""
    months = experience_months(profile)
    in_profile = numbers(json.dumps(profile.model_dump(exclude={"provenance"})))
    return in_profile | numbers(length_phrase(months)) | {str(months)}


def text_problems(where: str, text: str, allowed: set[str]) -> list[str]:
    problems = []
    if numbers(text) - allowed:
        problems.append(f"{where} contains a number that is not in the profile")
    if re.search(r"\b(familiar with|exposure to)\b", text, re.IGNORECASE):
        problems.append(f"{where} softens a claim with 'familiar with' or 'exposure to'")
    return problems
