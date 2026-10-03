import json
from pathlib import Path

from app.schemas.profile import MasterProfile

EXAMPLE = Path(__file__).parents[1] / "app" / "schemas" / "profile_schema.json"


def test_example_matches_model_exactly():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["certifications"][0]["source"] = (
        "upload"  # the file writes the enum as "upload|link|manual"
    )
    # extra="forbid" rejects example-only fields; equality rejects model-only fields
    assert MasterProfile.model_validate(data).model_dump() == data
