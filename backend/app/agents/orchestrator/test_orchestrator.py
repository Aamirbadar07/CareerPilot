import json

from app import sample
from app.agents.career_coach.prompt import SYSTEM_PROMPT as COACH
from app.agents.fit_scorer.prompt import SYSTEM_PROMPT as FIT
from app.agents.job_discovery import sources
from app.agents.job_discovery.prompt import SYSTEM_PROMPT as DISCOVERY
from app.agents.job_discovery.schema import RawPosting
from app.agents.linkedin_optimizer.prompt import SYSTEM_PROMPT as LINKEDIN
from app.agents.orchestrator.agent import Orchestrator
from app.agents.orchestrator.prompt import SYSTEM_PROMPT as ORCHESTRATOR
from app.agents.resume_analyzer.prompt import SYSTEM_PROMPT as ANALYZER
from app.agents.resume_tailor.prompt import TAILOR_PROMPT, VALIDATOR_PROMPT
from app.core import runs
from app.db import repositories as repo
from conftest import routed_llm

JOBS = sample.load("jobs.json")
FITS = sample.load("fits.json")
LUMEN = "https://example.com/sample-jobs/lumen-forge-genai-developer"
TAILORED = sample.load("tailored.json")[LUMEN]


def discovery(inputs: dict) -> str:
    if inputs["phase"].startswith("1"):
        return json.dumps({"queries": JOBS["queries"]})
    return json.dumps({"jobs": JOBS["jobs"]})


ROUTES = {
    ANALYZER: json.dumps(sample.load("analysis.json")),
    DISCOVERY: discovery,
    FIT: lambda inputs: json.dumps(FITS[inputs["job"]["url"]]),
    TAILOR_PROMPT: json.dumps(TAILORED["resume"]),
    VALIDATOR_PROMPT: json.dumps(TAILORED["validation"]),
    LINKEDIN: json.dumps(sample.load("linkedin.json")),
    COACH: json.dumps(sample.load("coach.json")),
}


def feed(monkeypatch):
    postings = [
        RawPosting(
            **{k: j.get(k) for k in ("url", "title", "company", "location", "salary")},
            posted="2099-01-01",
            source="feed",
            description=j["description"],
        )
        for j in JOBS["jobs"]
    ]
    monkeypatch.setattr(sources, "SOURCES", {"feed": lambda queries: postings})


def execute(sessions, routes, **state):
    run = runs.create()
    Orchestrator(routed_llm(routes), sessions, run).execute(state)
    return run


def outcome(run) -> list[tuple[str, str]]:
    return [(e["agent"], e["status"]) for e in run.events if e["status"] != "started"]


def test_full_run_from_a_resume(sessions, db, monkeypatch):
    feed(monkeypatch)
    run = execute(
        sessions,
        ROUTES,
        raw_resume_text=sample.text("resume.txt"),
        source_file="resume.pdf",
        linkedin_text=sample.text("linkedin.txt"),
    )

    assert run.done and run.profile_id
    assert sorted(outcome(run)) == sorted(
        [
            ("resume_analyzer", "succeeded"),
            ("job_discovery", "succeeded"),
            ("fit_scorer", "succeeded"),
            ("linkedin_optimizer", "succeeded"),
            ("career_coach", "succeeded"),
        ]
    )
    # every agent call is announced before it runs
    started = [e["agent"] for e in run.events if e["status"] == "started"]
    assert len(started) == 5 and started[0] == "resume_analyzer"
    order = [agent for agent, _ in outcome(run)]
    assert order.index("job_discovery") < order.index("fit_scorer") < order.index("career_coach")

    profile = repo.get_profile(db, run.profile_id)
    assert len(repo.list_artifacts(db, profile.profile_id, "fit_report")) == 6
    assert repo.get_artifact(db, profile.profile_id, "coaching_plan") is not None
    # resume_tailor never runs unasked
    assert repo.list_artifacts(db, profile.profile_id, "tailored_resume") == []
    detail = {e["agent"]: e["detail"] for e in run.events if e["status"] == "succeeded"}
    assert detail["fit_scorer"] == "6 jobs scored, 1 strong"


def test_tailor_runs_only_for_selected_jobs(sessions, db, mine):
    job_id = next(j["id"] for j in sample.jobs() if j["url"] == LUMEN)
    repo.delete_artifacts(db, mine, "tailored_resume")
    run = execute(
        sessions,
        ROUTES,
        profile_id=mine,
        selected_job_ids=[job_id],
        requested=["resume_tailor"],
    )
    assert outcome(run) == [("resume_tailor", "succeeded")]
    assert [a.ref for a in repo.list_artifacts(db, mine, "tailored_resume")] == [job_id]


def test_agent_failing_twice_is_degraded_and_the_run_continues(sessions, db, mine):
    routes = {k: v for k, v in ROUTES.items() if k is not LINKEDIN}  # the model is "down"
    repo.delete_artifacts(db, mine, "coaching_plan")
    run = execute(
        sessions,
        routes,
        profile_id=mine,
        linkedin_text="x" * 60,
        requested=["linkedin_optimizer", "career_coach"],
    )
    assert ("linkedin_optimizer", "failed") in outcome(run)
    assert ("career_coach", "succeeded") in outcome(run)
    assert run.done


def test_agent_with_missing_inputs_is_skipped_not_run(sessions, db):
    profile = sample.profile("empty")
    profile.target_roles = []
    repo.save_profile(db, profile)
    run = execute(sessions, ROUTES, profile_id="empty")
    assert outcome(run) == [
        ("job_discovery", "failed"),
        ("fit_scorer", "failed"),
        ("career_coach", "failed"),
    ]
    assert all("skipped: needs" in e["detail"] for e in run.events)


def test_model_router_may_reorder_but_only_among_runnable_agents(sessions, db, mine):
    repo.delete_artifacts(db, mine, "coaching_plan", "linkedin")
    answers = iter(["career_coach", "resume_analyzer", "linkedin_optimizer"])

    def decide(inputs: dict) -> str:
        assert set(inputs["runnable_now"]) <= {"linkedin_optimizer", "career_coach"}
        return json.dumps({"next": next(answers), "reason": "test"})

    run = execute(
        sessions,
        ROUTES | {ORCHESTRATOR: decide},
        profile_id=mine,
        linkedin_text="x" * 60,
        requested=["linkedin_optimizer", "career_coach"],
    )
    # the model put the coach first; pipeline order would have run LinkedIn first
    assert outcome(run) == [("career_coach", "succeeded"), ("linkedin_optimizer", "succeeded")]


def test_sse_stream_replays_and_resumes():
    run = runs.create()
    run.emit("a", "started")
    run.emit("a", "succeeded", "ok")
    run.profile_id = "p1"
    run.finish()
    frames = list(run.sse())
    assert (
        frames[0]
        == 'id: 0\nevent: progress\ndata: {"agent": "a", "status": "started", "detail": ""}\n\n'
    )
    assert frames[-1] == 'event: done\ndata: {"profile_id": "p1"}\n\n'
    assert len(list(run.sse(start=1))) == 2  # Last-Event-ID: 0 resumes after the first event
