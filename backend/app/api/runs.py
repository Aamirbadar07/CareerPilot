import threading

from fastapi import APIRouter, Depends, Form, Header, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.agents.orchestrator.agent import PIPELINE, Orchestrator
from app.api.deps import get_llm
from app.api.profiles import read_upload
from app.core import runs
from app.core.llm import LLM
from app.core.rate_limit import rate_limit
from app.db import repositories as repo
from app.db.session import SessionLocal, get_db
from app.sample import SAMPLE_ID

router = APIRouter(prefix="/api/runs")


def get_sessions():
    """The session factory the background run uses. Overridden in tests."""
    return SessionLocal


@router.post("", dependencies=[Depends(rate_limit(5, 3600))])
def start_run(
    file: UploadFile | None = None,
    profile_id: str | None = Form(default=None),
    linkedin_text: str | None = Form(default=None, max_length=30_000),
    selected_job_ids: list[str] = Form(default=[]),
    agents: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
    llm: LLM = Depends(get_llm),
    sessions=Depends(get_sessions),
):
    """One click: start every agent that has its inputs and return at once. Progress is
    read from /api/runs/{id}/stream. Start from a resume file (a new profile) or from an
    existing profile. `agents` narrows the run, which is how a failed step is retried."""
    state = {
        "linkedin_text": linkedin_text,
        "selected_job_ids": selected_job_ids,
        "requested": [a for a in PIPELINE if not agents or a in agents],
    }
    if file is not None:
        repo.purge_expired(db)
        state["source_file"], state["raw_resume_text"] = read_upload(file)
    elif profile_id and profile_id != SAMPLE_ID and repo.get_profile(db, profile_id):
        state["profile_id"] = profile_id
    elif profile_id == SAMPLE_ID:
        raise HTTPException(403, "The sample profile is read-only. Upload your own resume.")
    else:
        raise HTTPException(422, "Send a resume file or the id of an existing profile.")

    run = runs.create()
    run.profile_id = state.get("profile_id")
    orchestrator = Orchestrator(llm, sessions, run)
    threading.Thread(target=orchestrator.execute, args=(state,), daemon=True).start()
    return {"run_id": run.id}


def _run(run_id: str) -> runs.Run:
    run = runs.get(run_id)
    if run is None:
        raise HTTPException(404, "Run not found. Runs are forgotten when the server restarts.")
    return run


@router.get("/{run_id}")
def read_run(run_id: str):
    return _run(run_id).snapshot()


@router.get("/{run_id}/stream")
def stream(run_id: str, last_event_id: str | None = Header(default=None)):
    start = int(last_event_id) + 1 if last_event_id and last_event_id.isdigit() else 0
    return StreamingResponse(
        _run(run_id).sse(start),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
