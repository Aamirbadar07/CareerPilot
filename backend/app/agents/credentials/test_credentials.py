import copy
import json
from urllib.parse import parse_qs, urlparse

from app import sample
from app.agents.credentials.agent import propose_credential
from app.core.profile_ops import apply_credential
from conftest import fake_llm

PROFILE = sample.profile()
CERTIFICATE = sample.text("certificate.txt")
FIXTURE = sample.load("credential.json")


def propose(evidence=CERTIFICATE, url=None, source="upload", mutate=None, **kwargs):
    data = copy.deepcopy(FIXTURE)
    if mutate:
        mutate(data)
    return propose_credential(fake_llm(json.dumps(data)), PROFILE, evidence, url, source, **kwargs)


def test_certificate_becomes_a_verified_patch_with_code_owned_fields():
    proposal = propose(stale_resumes=["Job A (Acme)"], open_gaps=["AWS", "pytest"])
    cert = proposal.certification

    assert cert.id == "cert_2" and proposal.profile_patch.op == "add"
    assert (cert.verified, cert.source, cert.credential_id) == (True, "upload", "SAMPLE1234XYZ")
    assert proposal.needs_review == []
    # code, not the model, decides these three
    assert proposal.downstream.stale_resumes == ["Job A (Acme)"]
    assert proposal.downstream.roles_strengthened == ["AI Engineer", "Generative AI Developer"]
    assert proposal.confirmation_prompt == (
        'Add "AWS Certified AI Practitioner" (Amazon Web Services, 2026-08) as a verified '
        "certification covering: AI and ML fundamentals on AWS, Generative AI fundamentals."
    )
    query = parse_qs(urlparse(proposal.linkedin_add_url).query)
    assert query["name"] == ["AWS Certified AI Practitioner"]
    assert (query["issueYear"], query["issueMonth"]) == (["2026"], ["8"])
    assert query["certId"] == ["SAMPLE1234XYZ"]


def test_a_statement_alone_is_unverified_and_guessed_ids_are_dropped():
    proposal = propose(evidence="I passed the AWS Certified AI Practitioner exam.", source="manual")
    cert = proposal.certification
    assert cert.verified is False and cert.credential_id is None and cert.credential_url is None
    assert {"credential_id", "credential_url", "issuer"} <= set(proposal.needs_review)
    assert "as an unverified certification" in proposal.confirmation_prompt


def test_a_supplied_link_verifies_without_being_fetched():
    link = "https://www.credly.com/badges/sample-badge"
    proposal = propose(evidence="", url=link, source="link")
    assert proposal.certification.verified and proposal.certification.credential_url == link


def test_duplicate_becomes_an_update_of_the_existing_entry():
    def same(data):
        data["certification"]["name"] = "AWS Certified Cloud Practitioner"

    proposal = propose(mutate=same)
    assert proposal.duplicate_of == "cert_1" and proposal.profile_patch.op == "update"
    assert proposal.certification.id == "cert_1"
    assert proposal.confirmation_prompt.startswith("Update cert_1 to")


def test_applying_creates_a_new_version_with_evidenced_skills():
    updated = apply_credential(PROFILE, propose())
    assert updated.version == PROFILE.version + 1 and PROFILE.version == 1  # original untouched
    assert [c.id for c in updated.certifications] == ["cert_1", "cert_2"]
    new_skill = next(s for s in updated.skills if s.name == "Generative AI fundamentals")
    assert new_skill.evidence == ["cert_2"] and new_skill.verified
    entry = updated.provenance.change_log[-1]
    assert (entry.agent, entry.change, entry.approved_by_user) == (
        "credentials",
        "added cert_2",
        True,
    )
