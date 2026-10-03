from typing import TypedDict

from pydantic import BaseModel


class Decision(BaseModel):
    """The orchestrator model's output."""

    next: str
    input_keys: list[str] = []
    reason: str = ""
    missing: list[str] = []


class RunState(TypedDict, total=False):
    """LangGraph state for one run. Small on purpose: the master profile and every agent
    output live in the database, and nodes read them from there."""

    profile_id: str | None
    raw_resume_text: str | None
    source_file: str | None
    linkedin_text: str | None
    selected_job_ids: list[str]
    requested: list[str]  # agents this run may use
    finished: list[str]  # succeeded, degraded or skipped: will not run again
    degraded: list[str]
    next: str
