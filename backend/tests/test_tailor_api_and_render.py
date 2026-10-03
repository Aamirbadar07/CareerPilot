import json

import pytest

from app import sample
from app.agents.resume_tailor.agent import untailored
from app.agents.resume_tailor.schema import TailoredResume
from app.core import render
from conftest import fake_llm

URL = "https://example.com/sample-jobs/lumen-forge-genai-developer"
PROFILE = sample.profile()
SAMPLE = sample.load("tailored.json")[URL]
RESUME = TailoredResume(**SAMPLE["resume"])
JOB_ID = next(j["id"] for j in sample.jobs() if j["url"] == URL)
BASE = f"/api/profiles/sample/jobs/{JOB_ID}/tailor"


def pdf_available() -> bool:
    try:
        render.page_count("<p>x</p>")
    except render.PdfUnavailable:
        return False
    return True


needs_pdf = pytest.mark.skipif(not pdf_available(), reason="WeasyPrint native libraries missing")


def test_html_takes_facts_from_the_profile_and_escapes_content():
    html = render.render_html(PROFILE, RESUME)
    assert "Kestrel Data Labs" in html and "Feb 2026 - Jun 2026" in html
    assert "Pune Institute of Technology" in html and "CGPA 8.4" in html
    assert "AWS Certified Cloud Practitioner, Amazon Web Services" in html

    hostile = RESUME.model_copy(update={"summary": "<script>alert(1)</script>"})
    assert "<script>" not in render.render_html(PROFILE, hostile)


def test_unknown_ids_are_not_rendered():
    data = SAMPLE["resume"] | {"experience": [{"exp_id": "exp_404", "bullets": []}]}
    assert "Experience</h2>" not in render.render_html(PROFILE, TailoredResume(**data))


def test_tailor_endpoints(client, db):
    sample.seed(db)
    stored = client.get(BASE).json()
    assert stored["result"]["status"] == "tailored"
    assert stored["original"] == untailored(PROFILE).model_dump()
    assert "Lumen" not in client.get(f"{BASE}/html").text  # the resume, not the job
    assert "Asha Verma" in client.get(f"{BASE}/html").text

    client.llm = fake_llm(json.dumps(SAMPLE["resume"]), json.dumps(SAMPLE["validation"]))
    r = client.post(BASE)  # the fit report is seeded, so only tailor and validator are called
    assert r.status_code == 200 and r.json()["result"]["attempts"] == 1

    assert client.post("/api/profiles/sample/jobs/nope/tailor").status_code == 404
    expected = 200 if pdf_available() else 501
    assert client.get(f"{BASE}/pdf").status_code == expected


@needs_pdf
def test_pdf_is_one_page():
    html = render.render_html(PROFILE, RESUME)
    assert render.page_count(html) == 1
    assert render.render_pdf(html).startswith(b"%PDF")


@needs_pdf
def test_overflowing_resume_is_cut_to_one_page():
    long = RESUME.model_copy(deep=True)
    long.projects[0].bullets = long.projects[0].bullets * 40
    assert render.page_count(render.render_html(PROFILE, long)) > 1
    cut, html = render.fit_to_one_page(PROFILE, long)
    assert render.page_count(html) == 1
    assert len(cut.experience[0].bullets) == 3  # experience is cut last
