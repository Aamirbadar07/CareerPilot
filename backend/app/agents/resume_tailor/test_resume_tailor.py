import copy
import json

import pytest

from app import sample
from app.agents.fit_scorer.schema import FitReport
from app.agents.job_discovery.schema import Job
from app.agents.resume_tailor.agent import (
    experience_months,
    fabrications,
    tailor_resume,
    untailored,
)
from app.agents.resume_tailor.schema import TailoredResume
from conftest import fake_llm

URL = "https://example.com/sample-jobs/lumen-forge-genai-developer"
PROFILE = sample.profile()
JOB = next(Job(**j) for j in sample.jobs() if j["url"] == URL)
FIT = FitReport(**sample.load("fits.json")[URL])
SAMPLE = sample.load("tailored.json")[URL]
RESUME = json.dumps(SAMPLE["resume"])
PASS = json.dumps(SAMPLE["validation"])


def resume(mutate) -> TailoredResume:
    data = copy.deepcopy(SAMPLE["resume"])
    mutate(data)
    return TailoredResume(**data)


def failing_validation(claim: str, status: str = "UNSUPPORTED") -> str:
    finding = {"claim": claim, "status": status, "profile_evidence": None, "fix": "remove it"}
    return json.dumps({"verdict": "pass", "findings": [finding], "must_fix_count": 0})


def test_sample_resume_passes_both_guards():
    assert fabrications(PROFILE, TailoredResume(**SAMPLE["resume"])) == []
    result = tailor_resume(fake_llm(RESUME, PASS), PROFILE, JOB, FIT)
    assert (result.status, result.attempts, result.validation.verdict) == ("tailored", 1, "pass")
    assert result.model_dump() == SAMPLE  # the seeded demo data is what the pipeline produces


# Deliberately poisoned resumes: each adds one thing the profile does not contain.
POISONED = {
    "invented number": lambda d: d["experience"][0]["bullets"][0].update(
        text="Built a RAG pipeline serving 50,000 users."
    ),
    "inflated metric": lambda d: d["experience"][0]["bullets"][1].update(
        text="Scored 150 question-answer pairs and caught 80 hallucinated answers."
    ),
    "invented tool in skills": lambda d: d["skills"][0]["items"].append("Kubernetes"),
    "bullet with no source": lambda d: d["experience"][0]["bullets"].append(
        {"text": "Mentored interns.", "from_bullet": "b_9"}
    ),
    "invented employer": lambda d: d["experience"].append({"exp_id": "exp_7", "bullets": []}),
    "invented project": lambda d: d["projects"].append({"proj_id": "proj_9", "bullets": []}),
    "softened claim": lambda d: d.update(summary="Familiar with Kubernetes and Terraform."),
    "invented percentage": lambda d: d.update(summary="Improved accuracy by 35%."),
}


@pytest.mark.parametrize("name", list(POISONED))
def test_code_guard_catches_poisoned_resume(name):
    assert fabrications(PROFILE, resume(POISONED[name])), name


def test_code_guard_allows_honest_rewording_and_computed_length():
    honest = resume(
        lambda d: d.update(summary="5 months building RAG pipelines (vector database: pgvector).")
    )
    assert fabrications(PROFILE, honest) == []
    assert experience_months(PROFILE) == 5


def test_validator_verdict_is_derived_from_findings_not_trusted():
    """The model says "pass" but lists an unsupported claim: code overrides the verdict."""
    llm = fake_llm(RESUME, failing_validation("led a team of 5"), RESUME, PASS)
    result = tailor_resume(llm, PROFILE, JOB, FIT)
    assert (result.status, result.attempts) == ("tailored", 2)
    retry_input = json.loads(llm.calls[2][1][0]["content"])
    assert retry_input["validator_findings"][0]["claim"] == "led a team of 5"


def test_two_validator_failures_return_the_untailored_resume_with_a_reason():
    bad = failing_validation("production-grade system", "OVERSTATED")
    result = tailor_resume(fake_llm(RESUME, bad, RESUME, bad), PROFILE, JOB, FIT)
    assert result.status == "untailored"
    assert result.resume == untailored(PROFILE)
    assert "1 unsupported or overstated" in result.reason
    assert result.resume.experience[0].bullets[1].text.startswith("Responsible for")


def test_code_guard_failure_also_falls_back():
    poisoned = json.dumps(resume(POISONED["invented number"]).model_dump())
    result = tailor_resume(fake_llm(poisoned, poisoned), PROFILE, JOB, FIT)
    assert result.status == "untailored" and "number that is not in the profile" in result.reason
