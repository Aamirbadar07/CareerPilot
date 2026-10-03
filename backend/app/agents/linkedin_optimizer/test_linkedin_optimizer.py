import copy
import json

import pytest

from app import sample
from app.agents.linkedin_optimizer.agent import optimize_linkedin
from app.core.llm import LLMError
from conftest import fake_llm

PROFILE = sample.profile()
PASTED = sample.text("linkedin.txt")
FIXTURE = sample.load("linkedin.json")


def respond(mutate=None) -> str:
    data = copy.deepcopy(FIXTURE)
    if mutate:
        mutate(data)
    return json.dumps(data)


def test_sample_result_passes_and_strength_is_recomputed():
    def lie(data):
        data["profile_strength"]["score"] = 95

    result = optimize_linkedin(fake_llm(respond(lie)), PROFILE, PASTED)
    assert result.profile_strength.score == 23
    assert result.model_dump() == FIXTURE  # the seeded demo data is what the pipeline produces
    assert sum(s.pinned for s in result.skills_order) == 3


def test_contact_details_are_not_sent():
    llm = fake_llm(respond())
    optimize_linkedin(llm, PROFILE, PASTED)
    assert "asha.verma@example.com" not in llm.calls[0][1][0]["content"]


BAD = {
    "banned word": (
        lambda d: d["headline"].__setitem__(0, "Aspiring AI Engineer"),
        "aspiring",
    ),
    "long headline": (lambda d: d["headline"].__setitem__(1, "AI Engineer " * 30), "220"),
    "invented number": (
        lambda d: d["about"].__setitem__(1, "I served 50,000 users."),
        "number that is not in the profile",
    ),
    "invented skill": (
        lambda d: d["skills_order"].append({"name": "Kubernetes", "pinned": False}),
        "names no skill",
    ),
    "invented employer": (
        lambda d: d["experience_rewrites"][0].update(exp_id="exp_9"),
        "exp_id",
    ),
    "four pinned skills": (lambda d: d["skills_order"][3].update(pinned=True), "top 3"),
}


@pytest.mark.parametrize("name", list(BAD))
def test_guard_rejects(name):
    mutate, message = BAD[name]
    bad = respond(mutate)
    with pytest.raises(LLMError, match=message):
        optimize_linkedin(fake_llm(bad, bad), PROFILE, PASTED)


def test_numbers_from_the_pasted_linkedin_text_are_allowed():
    pasted = PASTED + "\nVolunteer: taught 40 students Python."

    def cite(data):
        data["about"][3] += " I also taught 40 students Python."

    assert optimize_linkedin(fake_llm(respond(cite)), PROFILE, pasted)
