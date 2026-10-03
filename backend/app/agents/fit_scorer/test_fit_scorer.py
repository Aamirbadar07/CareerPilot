import copy
import json

import pytest

from app import sample
from app.agents.fit_scorer.agent import profile_for_llm, score_job, score_jobs
from app.agents.fit_scorer.schema import band_for
from app.agents.job_discovery.schema import Job
from app.core.llm import LLMError
from conftest import fake_llm

PROFILE = sample.profile()
JOBS = {j["url"]: Job(**j) for j in sample.jobs()}
FITS = sample.load("fits.json")
LUMEN = "https://example.com/sample-jobs/lumen-forge-genai-developer"
TALLYROOT = "https://example.com/sample-jobs/tallyroot-python-backend-developer"


def respond(url: str, mutate=None) -> str:
    data = copy.deepcopy(FITS[url])
    if mutate:
        mutate(data)
    return json.dumps(data)


@pytest.mark.parametrize("url", list(FITS))
def test_every_sample_report_survives_the_code_checks_unchanged(url):
    """The seeded demo data must be what the pipeline itself would produce."""
    report = score_job(fake_llm(respond(url)), PROFILE, JOBS[url])
    assert report.model_dump() == FITS[url]


def test_score_and_band_are_computed_in_code():
    def lie(data):
        data["score"], data["band"] = 97, "Poor"

    report = score_job(fake_llm(respond(LUMEN, lie)), PROFILE, JOBS[LUMEN])
    assert (report.score, report.band) == (89, "Strong")


def test_missing_must_have_caps_the_score_at_60():
    report = score_job(fake_llm(respond(TALLYROOT)), PROFILE, JOBS[TALLYROOT])
    assert sum(d.score for d in report.dimensions) == 73
    assert (report.score, report.band, report.capped) == (60, "Competitive", True)


def test_skill_without_profile_evidence_cannot_be_counted():
    def invent(data):
        data["matched"].append({"skill": "Kubernetes", "evidence": "b_77"})

    bad = respond(LUMEN, invent)
    with pytest.raises(LLMError, match="evidence"):
        score_job(fake_llm(bad, bad), PROFILE, JOBS[LUMEN])


@pytest.mark.parametrize(
    "verdict",
    ["You have a 70% chance of an interview.", "The odds of getting hired here are good."],
)
def test_hire_probability_is_rejected(verdict):
    def predict(data):
        data["verdict"] = verdict

    bad = respond(LUMEN, predict)
    with pytest.raises(LLMError, match="probability"):
        score_job(fake_llm(bad, bad), PROFILE, JOBS[LUMEN])


def test_percentages_that_are_not_predictions_are_allowed():
    def describe(data):
        data["dimensions"][0]["why"] = "Covers 100% of the must-haves."

    assert score_job(fake_llm(respond(LUMEN, describe)), PROFILE, JOBS[LUMEN]).score == 89


def test_wrong_weights_are_rejected():
    def reweight(data):
        data["dimensions"][0]["max"] = 50

    bad = respond(LUMEN, reweight)
    with pytest.raises(LLMError, match="weighted"):
        score_job(fake_llm(bad, bad), PROFILE, JOBS[LUMEN])


def test_contact_details_are_not_sent_to_the_model():
    llm = fake_llm(respond(LUMEN))
    score_job(llm, PROFILE, JOBS[LUMEN])
    sent = llm.calls[0][1][0]["content"]
    assert "asha.verma@example.com" not in sent and "90000" not in sent
    assert profile_for_llm(PROFILE)["identity"]["full_name"] == "Asha Verma"


def test_one_failing_job_does_not_block_the_batch():
    class Routed:
        """score_jobs runs in threads, so answer by job rather than by call order."""

        def complete(self, system, inputs, schema, **kwargs):
            url = inputs["job"]["url"]
            if url == TALLYROOT:
                raise LLMError("boom")
            return fake_llm(respond(url)).complete(system, inputs, schema, **kwargs)

    results = score_jobs(Routed(), PROFILE, list(JOBS.values()))
    assert results[JOBS[TALLYROOT].id] is None
    assert sum(r is not None for r in results.values()) == 5


@pytest.mark.parametrize(
    ("score", "band"),
    [(100, "Strong"), (75, "Strong"), (74, "Competitive"), (55, "Competitive")]
    + [(54, "Stretch"), (35, "Stretch"), (34, "Poor"), (0, "Poor")],
)
def test_band_boundaries(score, band):
    assert band_for(score) == band
