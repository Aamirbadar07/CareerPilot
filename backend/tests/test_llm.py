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


def test_google_provider_maps_roles_system_prompt_and_usage(monkeypatch):
    from types import SimpleNamespace as NS

    from app.core import llm as llm_module

    monkeypatch.setattr(llm_module.settings, "llm_provider", "google")
    seen = {}

    def generate_content(model, contents, config):
        seen.update(model=model, contents=contents, config=config)
        bad = len(contents) == 1  # first answer is invalid, so the retry path runs too
        return NS(
            text='{"name": "a"}' if bad else GOOD,
            candidates=[NS(finish_reason=NS(name="STOP"))],
            usage_metadata=NS(
                prompt_token_count=10, candidates_token_count=4, thoughts_token_count=1
            ),
        )

    client = NS(models=NS(generate_content=generate_content))
    model = llm_module.LLM(client=client)
    assert model.complete("the system prompt", {"x": 1}, Out) == Out(name="a", n=1)

    assert seen["model"] == llm_module.settings.google_model
    assert [c["role"] for c in seen["contents"]] == ["user", "model", "user"]
    assert seen["config"].system_instruction == "the system prompt"
    assert seen["config"].response_mime_type == "application/json"
    assert model.usage == {"calls": 2, "input_tokens": 20, "output_tokens": 10}


def test_google_provider_fails_loudly_when_cut_off_or_unconfigured(monkeypatch):
    from types import SimpleNamespace as NS

    from app.core import llm as llm_module

    monkeypatch.setattr(llm_module.settings, "llm_provider", "google")
    monkeypatch.setattr(llm_module.settings, "google_api_key", "")
    with pytest.raises(LLMError, match="no Google API key"):
        llm_module.LLM().complete("sys", "x", Out)

    cut = NS(text="", candidates=[NS(finish_reason=NS(name="MAX_TOKENS"))], usage_metadata=None)
    client = NS(models=NS(generate_content=lambda **kwargs: cut))
    with pytest.raises(LLMError, match="MAX_TOKENS"):
        llm_module.LLM(client=client).complete("sys", "x", Out)
