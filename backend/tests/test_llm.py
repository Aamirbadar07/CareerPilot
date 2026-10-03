import json

import pytest
from pydantic import BaseModel

from app.core.llm import LLMError, repair_json
from app.db.repositories import DbCache
from conftest import fake_llm


class Out(BaseModel):
    name: str
    n: int


GOOD = '{"name": "a", "n": 1}'


@pytest.mark.parametrize(
    "raw",
    [
        GOOD,
        f"```json\n{GOOD}\n```",
        f"Here is the JSON:\n{GOOD}\nHope that helps.",
        '{"name": "a", "n": 1,}',
    ],
)
def test_repair_json(raw):
    assert json.loads(repair_json(raw)) == {"name": "a", "n": 1}


def test_retries_once_with_the_validation_error():
    llm = fake_llm('{"name": "a"}', GOOD)
    assert llm.complete("sys", {"x": 1}, Out) == Out(name="a", n=1)
    retry_messages = llm.calls[1][1]
    assert len(retry_messages) == 3
    assert "missing" in retry_messages[2]["content"]


def test_fails_loudly_after_second_bad_output_without_leaking_content():
    llm = fake_llm("not json SECRET-RESUME-TEXT", '{"name": "SECRET-RESUME-TEXT"}')
    with pytest.raises(LLMError) as err:
        llm.complete("sys", "input", Out)
    assert "SECRET" not in str(err.value)


def test_cache_hit_skips_the_model(sessions):
    llm = fake_llm(GOOD)
    llm.cache = DbCache(sessions)
    first = llm.complete("sys", {"b": 2, "a": 1}, Out)
    second = llm.complete("sys", {"a": 1, "b": 2}, Out)  # key order must not matter
    assert first == second
    assert len(llm.calls) == 1
