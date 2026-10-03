import re

from app.agents.fit_scorer.agent import profile_for_llm
from app.agents.linkedin_optimizer.prompt import OUTPUT_SHAPE, SYSTEM_PROMPT
from app.agents.linkedin_optimizer.schema import LinkedInOptimizationResult
from app.core import guard
from app.core.llm import LLM
from app.schemas.profile import MasterProfile

_BANNED = re.compile(r"\b(aspiring|passionate)\b", re.IGNORECASE)


def optimize_linkedin(
    llm: LLM, profile: MasterProfile, linkedin_text: str
) -> LinkedInOptimizationResult:
    """Copy-paste-ready LinkedIn text. The app never edits LinkedIn itself (CLAUDE.md rule 5)."""
    exp_ids = {e.id for e in profile.experience}
    known = guard.known_skills(profile)
    # the pasted LinkedIn text is the candidate's own writing, so its numbers are allowed too
    allowed = guard.allowed_numbers(profile) | guard.numbers(linkedin_text)

    def check(result: LinkedInOptimizationResult) -> None:
        problems = []
        texts = {}
        for i, headline in enumerate(result.headline):
            texts[f"headline[{i}]"] = headline
            if len(headline) >= 220:
                problems.append(f"headline[{i}] is 220 characters or longer")
            if _BANNED.search(headline):
                problems.append(f"headline[{i}] uses 'aspiring' or 'passionate'")
        for i, paragraph in enumerate(result.about):
            texts[f"about[{i}]"] = paragraph
        for i, rewrite in enumerate(result.experience_rewrites):
            if rewrite.exp_id not in exp_ids:
                problems.append(f"experience_rewrites[{i}].exp_id is not in the profile")
            texts[f"experience_rewrites[{i}].scope"] = rewrite.scope
            for j, bullet in enumerate(rewrite.bullets):
                texts[f"experience_rewrites[{i}].bullets[{j}]"] = bullet
        for i, skill in enumerate(result.skills_order):
            if not guard.names_known_skill(skill.name, known):
                problems.append(f"skills_order[{i}] names no skill that is in the profile")
        if sum(s.pinned for s in result.skills_order) != min(3, len(result.skills_order)):
            problems.append("skills_order must flag exactly the top 3 as pinned")
        for where, text in texts.items():
            problems += guard.text_problems(where, text, allowed)
        if problems:
            raise ValueError("; ".join(problems[:8]))

    result = llm.complete(
        SYSTEM_PROMPT,
        {
            "master_profile": profile_for_llm(profile),
            "linkedin_text": linkedin_text,
            "target_roles": [r.model_dump() for r in profile.target_roles],
            "experience_length": guard.length_phrase(guard.experience_months(profile)),
            "output_shape": OUTPUT_SHAPE,
        },
        LinkedInOptimizationResult,
        profile_id=profile.profile_id,
        check=check,
    )
    strength = result.profile_strength
    strength.score = sum(c.score for c in strength.components)  # arithmetic is ours
    return result
