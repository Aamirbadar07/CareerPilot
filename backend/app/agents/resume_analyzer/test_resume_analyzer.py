import copy
import json

import pytest

from app import sample
from app.agents.resume_analyzer.agent import analyze_resume
from app.core.llm import LLMError
from conftest import fake_llm

RESUME = sample.text("resume.txt")
RESPONSE = sample.load("analysis.json")


def respond(mutate=None) -> str:
    data = copy.deepcopy(RESPONSE)
    if mutate:
        mutate(data)
    return json.dumps(data)


def test_builds_a_profile_owned_by_code():
    llm = fake_llm(respond())
    result = analyze_resume(llm, RESUME, "resume.pdf")
    profile = result.master_profile

    assert profile.profile_id != "sample" and len(profile.profile_id) == 36
    assert profile.version == 1
    assert profile.provenance.source_file == "resume.pdf"
    assert profile.provenance.change_log[0].agent == "resume_analyzer"
    assert profile.experience[0].company == "Kestrel Data Labs"
    assert json.loads(llm.calls[0][1][0]["content"])["raw_resume_text"] == RESUME


def test_ats_score_is_recomputed_from_components():
    def lie(data):
        data["ats"]["score"] = 99

    result = analyze_resume(fake_llm(respond(lie)), RESUME, "resume.pdf")
    assert result.ats.score == 73


def test_skill_without_evidence_fails_the_request():
    def invent(data):
        data["master_profile"]["skills"].append(
            {"name": "Kubernetes", "category": "devops", "evidence": ["b_99"]}
        )

    bad = respond(invent)
    with pytest.raises(LLMError, match="evidence"):
        analyze_resume(fake_llm(bad, bad), RESUME, "resume.pdf")


def test_weak_bullet_must_point_at_a_real_bullet():
    def dangle(data):
        data["weak_bullets"][0]["bullet_id"] = "b_404"

    bad = respond(dangle)
    with pytest.raises(LLMError, match="weak_bullets"):
        analyze_resume(fake_llm(bad, bad), RESUME, "resume.pdf")


def test_retry_recovers_when_the_model_fixes_its_output():
    def invent(data):
        data["master_profile"]["skills"].append({"name": "Go", "category": "language"})

    result = analyze_resume(fake_llm(respond(invent), respond()), RESUME, "resume.pdf")
    assert "Go" not in [s.name for s in result.master_profile.skills]
