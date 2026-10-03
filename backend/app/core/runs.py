"""In-memory registry of pipeline runs and their progress events, read by the SSE endpoint."""

import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from uuid import uuid4

# ponytail: runs live in this process's memory (CLAUDE.md: in-process tasks for the MVP).
# A restart forgets them and a second worker cannot see them. Move to Redis with Celery.
_RUNS: dict[str, "Run"] = {}
_MAX_RUNS = 200
HEARTBEAT_SECONDS = 15


@dataclass
class Run:
    id: str = field(default_factory=lambda: uuid4().hex)
    events: list[dict] = field(default_factory=list)
    done: bool = False
    profile_id: str | None = None
    _changed: threading.Condition = field(default_factory=threading.Condition)

    def emit(self, agent: str, status: str, detail: str = "") -> None:
        """Progress events in the orchestrator's shape: {agent, status, detail}."""
        with self._changed:
            self.events.append({"agent": agent, "status": status, "detail": detail})
            self._changed.notify_all()

    def finish(self) -> None:
        with self._changed:
            self.done = True
            self._changed.notify_all()

    def snapshot(self) -> dict:
        return {
            "run_id": self.id,
            "done": self.done,
            "profile_id": self.profile_id,
            "events": list(self.events),
        }

    def sse(self, start: int = 0) -> Iterator[str]:
        """Server-Sent Events from event `start` until the run ends. The event id is its
        index, so a browser that reconnects sends Last-Event-ID and misses nothing."""
        sent = start
        while True:
            with self._changed:
                if sent >= len(self.events) and not self.done:
                    self._changed.wait(HEARTBEAT_SECONDS)
                batch, finished = self.events[sent:], self.done
            for event in batch:
                yield f"id: {sent}\nevent: progress\ndata: {json.dumps(event)}\n\n"
                sent += 1
            if finished and sent >= len(self.events):
                yield f"event: done\ndata: {json.dumps({'profile_id': self.profile_id})}\n\n"
                return
            if not batch:
                yield ": keep-alive\n\n"  # stops proxies closing an idle stream


def create() -> Run:
    while len(_RUNS) >= _MAX_RUNS:
        _RUNS.pop(next(iter(_RUNS)))  # dicts keep insertion order: drop the oldest
    run = Run()
    _RUNS[run.id] = run
    return run


def get(run_id: str) -> Run | None:
    return _RUNS.get(run_id)
