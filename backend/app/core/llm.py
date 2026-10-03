import hashlib
import json
import re
from typing import Protocol, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from app.core.config import settings

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Raised when the model cannot produce valid output. Never carries prompt or response
    text, because those hold resume content (CLAUDE.md rule 6)."""


class Cache(Protocol):
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str, profile_id: str | None = None) -> None: ...


def repair_json(text: str) -> str:
    """Recover a JSON document from typical model slips: code fences, prose around the
    object, trailing commas."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    end = max(text.rfind("}"), text.rfind("]"))
    if starts and end > min(starts):
        text = text[min(starts) : end + 1]
    return re.sub(r",\s*([}\]])", r"\1", text)


def _problems(e: ValidationError | json.JSONDecodeError) -> str:
    if isinstance(e, ValidationError):
        return json.dumps(e.errors(include_input=False, include_url=False), default=str)
    return f"invalid JSON: {e.msg} at line {e.lineno} column {e.colno}"


class LLM:
    def __init__(self, client: anthropic.Anthropic | None = None, cache: Cache | None = None):
        self._client = client
        self.cache = cache
        self.model = settings.anthropic_model

    def _raw(self, system: str, messages: list[dict]) -> str:
        if self._client is None:
            # api_key=None lets the SDK resolve credentials from the environment
            self._client = anthropic.Anthropic(
                api_key=settings.anthropic_api_key or None, max_retries=3
            )
        # streamed so long outputs (a full profile) cannot hit the HTTP timeout
        try:
            with self._client.messages.stream(
                model=self.model, max_tokens=32000, system=system, messages=messages
            ) as stream:
                message = stream.get_final_message()
        except anthropic.AnthropicError as e:  # the SDK has already retried what is retryable
            raise LLMError(f"model call failed: {type(e).__name__}") from None
        except TypeError as e:  # the SDK raises a bare TypeError when it finds no credentials
            if "authentication" not in str(e):
                raise
            raise LLMError("no Anthropic credentials configured") from None
        if message.stop_reason in ("max_tokens", "refusal"):
            raise LLMError(f"model stopped early: {message.stop_reason}")
        return "".join(block.text for block in message.content if block.type == "text")

    def complete(
        self, system: str, inputs: dict | str, schema: type[T], profile_id: str | None = None
    ) -> T:
        """One agent call: JSON in, validated `schema` out. A parse or validation failure is
        retried once with the error, then raised (CLAUDE.md rule 3)."""
        user = inputs if isinstance(inputs, str) else json.dumps(inputs, sort_keys=True)
        key = hashlib.sha256(f"{self.model}\x00{system}\x00{user}".encode()).hexdigest()
        if self.cache and (hit := self.cache.get(key)) is not None:
            return schema.model_validate_json(hit)

        messages = [{"role": "user", "content": user}]
        for attempt in (1, 2):
            raw = self._raw(system, messages)
            try:
                result = schema.model_validate(json.loads(repair_json(raw)))
            except (ValidationError, json.JSONDecodeError) as e:
                problems = _problems(e)
                if attempt == 2:
                    raise LLMError(f"{schema.__name__} invalid after retry: {problems}") from None
                messages += [
                    {"role": "assistant", "content": raw},
                    {
                        "role": "user",
                        "content": "Your output failed validation:\n"
                        f"{problems}\nReturn the corrected JSON only.",
                    },
                ]
                continue
            if self.cache:
                self.cache.set(key, result.model_dump_json(), profile_id)
            return result
        raise AssertionError("unreachable")
