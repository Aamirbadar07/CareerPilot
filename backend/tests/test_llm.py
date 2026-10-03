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


def test_google_provider_waits_and_retries_when_rate_limited(monkeypatch):
    from types import SimpleNamespace as NS

    from app.core import llm as llm_module

    monkeypatch.setattr(llm_module.settings, "llm_provider", "google")
    waits = []
    monkeypatch.setattr(llm_module.time, "sleep", waits.append)
    limited = llm_module.genai_errors.ClientError(
        429, {"error": {"message": "Quota exceeded. Please retry in 12.5s.", "status": "X"}}
    )
    busy = llm_module.genai_errors.ServerError(503, {"error": {"message": "overloaded"}})
    ok = NS(
        text=GOOD,
        candidates=[NS(finish_reason=NS(name="STOP"))],
        usage_metadata=NS(prompt_token_count=1, candidates_token_count=1, thoughts_token_count=0),
    )
    answers = iter([limited, busy, ok])

    def generate_content(**kwargs):
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    client = NS(models=NS(generate_content=generate_content))
    assert llm_module.LLM(client=client).complete("sys", "x", Out) == Out(name="a", n=1)
    assert waits == [13.5, 4.0]  # the server's delay plus a second, then exponential

    denied = llm_module.genai_errors.ClientError(403, {"error": {"message": "bad key"}})
    client = NS(models=NS(generate_content=lambda **kwargs: (_ for _ in ()).throw(denied)))
    with pytest.raises(LLMError, match="403"):  # not retryable: fails at once
        llm_module.LLM(client=client).complete("sys", "x", Out)
    assert len(waits) == 2


def test_google_daily_quota_fails_at_once_instead_of_retrying(monkeypatch):
    from types import SimpleNamespace as NS

    from app.core import llm as llm_module

    monkeypatch.setattr(llm_module.settings, "llm_provider", "google")
    monkeypatch.setattr(llm_module.time, "sleep", lambda s: pytest.fail("must not wait"))
    calls = []
    spent = llm_module.genai_errors.ClientError(
        429, {"error": {"message": "You exceeded your current quota. Please retry in 24337.5s."}}
    )

    def generate_content(**kwargs):
        calls.append(1)
        raise spent

    client = NS(models=NS(generate_content=generate_content))
    with pytest.raises(LLMError, match="daily quota used up.*6.8 h"):
        llm_module.LLM(client=client).complete("sys", "x", Out)
    assert len(calls) == 1
