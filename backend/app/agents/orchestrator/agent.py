import logging
from collections.abc import Callable
from functools import partial

from langgraph.graph import END, START, StateGraph

from app import services
from app.agents.orchestrator.prompt import SYSTEM_PROMPT
from app.agents.orchestrator.schema import Decision, RunState
from app.core.llm import LLM, LLMError
from app.core.runs import Run
from app.db import repositories as repo

log = logging.getLogger("careerpilot.orchestrator")

# The agents a run can drive, in the order code falls back to. `credentials` is not here: it
# needs a credential and the user's confirmation, so it runs from its own endpoint.
PIPELINE = [
    "resume_analyzer",
    "job_discovery",
    "fit_scorer",
    "resume_tailor",
    "linkedin_optimizer",
    "career_coach",
]
# An agent waits for these to finish (or be skipped) so it sees their output.
AFTER = {
    "job_discovery": ["resume_analyzer"],
    "fit_scorer": ["resume_analyzer", "job_discovery"],
    "resume_tailor": ["resume_analyzer", "fit_scorer"],
    "linkedin_optimizer": ["resume_analyzer"],
    "career_coach": ["resume_analyzer", "fit_scorer"],
}


class Orchestrator:
    """Runs the agents as a LangGraph state machine: a router node chooses the next agent,
    the agent node runs it, control returns to the router.

    The router asks the orchestrator model which agent is next, but only among agents whose
    inputs code has verified are present. A wrong, missing or failed answer falls back to
    pipeline order, so the model can reorder the run but cannot break it."""

    def __init__(self, llm: LLM, sessions: Callable, run: Run):
        self.llm, self.sessions, self.run = llm, sessions, run
        graph = StateGraph(RunState)
        graph.add_node("router", self._route)
        for agent in PIPELINE:
            graph.add_node(agent, partial(self._agent_node, agent))
            graph.add_edge(agent, "router")
        graph.add_edge(START, "router")
        graph.add_conditional_edges(
            "router", lambda state: state["next"], {**{a: a for a in PIPELINE}, "done": END}
        )
        self.graph = graph.compile()

    def execute(self, state: RunState) -> None:
        state = {"finished": [], "degraded": [], "selected_job_ids": [], **state}
        state.setdefault("requested", list(PIPELINE))
        try:
            self.graph.invoke(state, {"recursion_limit": 4 * len(PIPELINE)})
        except Exception:
            log.exception("run %s crashed", self.run.id)
            self.run.emit("orchestrator", "failed", "The run stopped unexpectedly.")
        finally:
            self.run.finish()

    # ---- routing -------------------------------------------------------------------------

    def _inputs(self, state: RunState) -> dict[str, bool]:
        """Which inputs exist right now. The orchestrator prompt's `needs:` column, checked."""
        profile_id = state.get("profile_id")
        with self.sessions() as db:
            profile = repo.get_profile(db, profile_id) if profile_id else None
            jobs = fits = False
            if profile:
                jobs = bool(services.stored_jobs(db, profile))
                fits = bool(services.current_fits(db, profile))
        return {
            "raw_resume_text": bool(state.get("raw_resume_text")),
            "master_profile": profile is not None,
            "target_roles": bool(profile and profile.target_roles),
            "linkedin_text": bool(state.get("linkedin_text")),
            "job": jobs,
            "fit_report": fits,
            "selected_jobs": bool(state.get("selected_job_ids")),
        }

    @staticmethod
    def _needs(agent: str) -> list[str]:
        return {
            "resume_analyzer": ["raw_resume_text"],
            "job_discovery": ["master_profile", "target_roles"],
            "fit_scorer": ["master_profile", "job"],
            "resume_tailor": ["master_profile", "job", "selected_jobs"],
            "linkedin_optimizer": ["master_profile", "linkedin_text"],
            "career_coach": ["master_profile", "fit_report"],
        }[agent]

    def _route(self, state: RunState) -> dict:
        have = self._inputs(state)
        finished = list(state["finished"])
        # pipeline order, so an upstream agent skipped in this pass unblocks its dependants
        pending = [a for a in PIPELINE if a in state["requested"] and a not in finished]

        # An agent whose inputs can no longer appear is skipped, loudly, and never blocks.
        waiting = []
        for agent in pending:
            upstream_done = all(
                dep in finished or dep not in state["requested"] for dep in AFTER.get(agent, [])
            )
            missing = [key for key in self._needs(agent) if not have[key]]
            if upstream_done and missing:
                if agent in ("resume_analyzer", "resume_tailor", "linkedin_optimizer"):
                    finished.append(agent)  # optional input not supplied: nothing to report
                    continue
                self.run.emit(agent, "failed", f"skipped: needs {', '.join(missing)}")
                finished.append(agent)
            elif upstream_done:
                waiting.append(agent)
        if not waiting:
            return {"next": "done", "finished": finished}

        choice = waiting[0]
        if len(waiting) > 1:
            try:
                decision = self.llm.complete(
                    SYSTEM_PROMPT,
                    {
                        "available_inputs": sorted(k for k, v in have.items() if v),
                        "finished": finished,
                        "degraded": state["degraded"],
                        "runnable_now": waiting,
                    },
                    Decision,
                )
                if decision.next in waiting:
                    choice = decision.next
            except LLMError:
                pass  # no model, no problem: pipeline order is always valid
        return {"next": choice, "finished": finished}

    # ---- agent nodes ---------------------------------------------------------------------

    def _agent_node(self, agent: str, state: RunState) -> dict:
        """Run one agent with the orchestrator's failure rule: a second failure marks the
        branch degraded and the run continues."""
        self.run.emit(agent, "started")
        update: dict = {"finished": [*state["finished"], agent]}
        for attempt in (1, 2):
            try:
                with self.sessions() as db:
                    detail, changes = getattr(self, f"_{agent}")(db, state)
            except Exception as e:  # noqa: BLE001 - any failure degrades the branch, never the run
                log.warning("%s attempt %d failed: %s", agent, attempt, type(e).__name__)
                if attempt == 2:
                    self.run.emit(agent, "failed", "failed twice; continuing without it")
                    update["degraded"] = [*state["degraded"], agent]
                continue
            self.run.emit(agent, "succeeded", detail)
            update |= changes
            break
        return update

    def _profile(self, db, state: RunState):
        return repo.get_profile(db, state["profile_id"])

    def _resume_analyzer(self, db, state):
        result = services.ingest_resume(
            db, self.llm, state["raw_resume_text"], state.get("source_file") or "resume"
        )
        profile = result.master_profile
        self.run.profile_id = profile.profile_id
        detail = f"ATS score {result.ats.score}, {len(result.weak_bullets)} weak bullets"
        return detail, {"profile_id": profile.profile_id, "raw_resume_text": None}

    def _job_discovery(self, db, state):
        result = services.discover(db, self.llm, self._profile(db, state))
        return f"{len(result.jobs)} jobs kept, {len(result.dropped)} dropped", {}

    def _fit_scorer(self, db, state):
        fits, failed = services.score_pending(db, self.llm, self._profile(db, state))
        if failed and not fits:
            raise LLMError("every job failed to score")
        strong = sum(f["band"] == "Strong" for f in fits.values())
        detail = f"{len(fits)} jobs scored, {strong} strong"
        return detail + (f", {len(failed)} failed" if failed else ""), {}

    def _resume_tailor(self, db, state):
        profile = self._profile(db, state)
        results = [
            services.tailor_job(db, self.llm, profile, job_id)
            for job_id in state["selected_job_ids"]
        ]
        tailored = sum(r.status == "tailored" for r in results)
        return f"{tailored} of {len(results)} resumes tailored and validated", {}

    def _linkedin_optimizer(self, db, state):
        result = services.run_linkedin(
            db, self.llm, self._profile(db, state), state["linkedin_text"]
        )
        return f"profile strength {result.profile_strength.score}", {}

    def _career_coach(self, db, state):
        plan = services.run_coach(db, self.llm, self._profile(db, state))
        return plan.one_line_verdict, {}
