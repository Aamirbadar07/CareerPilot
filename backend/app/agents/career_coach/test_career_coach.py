import copy
import json

import pytest

from app import sample
from app.agents.career_coach.agent import coach
from app.agents.fit_scorer.schema import FitReport
from app.agents.job_discovery.schema import Job
from app.core.llm import LLMError
from conftest import fake_llm

PROFILE = sample.profile()
FITS = sample.load("fits.json")
SCORED = [(Job(**j), FitReport(**FITS[j["url"]])) for j in sample.jobs()]
FIXTURE = sample.load("coach.json")


def respond(mutate=None) -> str:
    data = copy.deepcopy(FIXTURE)
    if mutate:
        mutate(data)
    return json.dumps(data)


def test_sample_plan_passes_and_counts_come_from_the_fit_reports():
    def lie(data):
        data["pattern_gaps"][0].update(blocks_n_jobs=6, pct_of_targets=100)
        data["pattern_gaps"].append(
            {
                "skill": "Rust",
                "blocks_n_jobs": 4,
                "pct_of_targets": 70,
                "acquisition_difficulty": "high",
            }
        )

    plan = coach(fake_llm(respond(lie)), PROFILE, SCORED)
    assert plan.model_dump() == FIXTURE  # counts recomputed; the invented gap is gone
    assert [(g.skill, g.blocks_n_jobs, g.pct_of_targets) for g in plan.pattern_gaps] == [
        ("AWS (hands-on)", 3, 50),
        ("agents / tool calling", 2, 33),
        ("pytest", 1, 17),
    ]


BAD = {
    "four actions": (lambda d: d["plan"].pop(), "5"),
    "unordered ranks": (lambda d: d["plan"][0].update(rank=3), "ranked 1 to 5"),
    "two large items": (
        lambda d: [d["plan"][i].update(effort_hours=80) for i in (0, 3)],
        "large",
    ),
    "invented job": (
        lambda d: d["plan"][0]["jobs_unlocked"].append("Staff Engineer (Nowhere Inc)"),
        "not in fit_reports",
    ),
}


@pytest.mark.parametrize("name", list(BAD))
def test_check_rejects(name):
    mutate, message = BAD[name]
    bad = respond(mutate)
    with pytest.raises(LLMError, match=message):
        coach(fake_llm(bad, bad), PROFILE, SCORED)
