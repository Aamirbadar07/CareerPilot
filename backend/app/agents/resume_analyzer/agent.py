import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.agents.resume_analyzer.prompt import SYSTEM_PROMPT
from app.agents.resume_analyzer.schema import ResumeAnalysisResult
from app.core.llm import LLM
from app.schemas.profile import ChangeLogEntry, Provenance

# The prompt writes master_profile as {...}; the model needs the actual shape.
_SHAPE = json.loads(
    (Path(__file__).parents[2] / "schemas" / "profile_schema.json").read_text(encoding="utf-8")
)


def analyze_resume(llm: LLM, raw_resume_text: str, source_file: str) -> ResumeAnalysisResult:
    profile_id = str(uuid4())
    result = llm.complete(
        SYSTEM_PROMPT,
        {"master_profile_shape": _SHAPE, "raw_resume_text": raw_resume_text},
        ResumeAnalysisResult,
        profile_id=profile_id,
    )
    now = datetime.now(UTC).isoformat()
    profile = result.master_profile
    profile.profile_id = profile_id
    profile.version = 1
    profile.updated_at = now
    profile.provenance = Provenance(
        source_file=source_file,
        parsed_at=now,
        change_log=[
            ChangeLogEntry(
                version=1,
                agent="resume_analyzer",
                change="created from uploaded resume",
                at=now,
                approved_by_user=True,
            )
        ],
    )
    if not profile.target_roles and result.target_roles:
        from app.schemas.profile import TargetRole

        profile.target_roles = [
            TargetRole(title=r.title, priority=i + 1) for i, r in enumerate(result.target_roles)
        ]
    return result
