import hashlib
import json
import re
import threading
from collections.abc import Callable
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


def _problems(e: Exception) -> str:
    if isinstance(e, ValidationError):
        return json.dumps(e.errors(include_input=False, include_url=False), default=str)
    if isinstance(e, json.JSONDecodeError):
        return f"invalid JSON: {e.msg} at line {e.lineno} column {e.colno}"
    return str(e)  # a ValueError raised by an agent's check


class LLM:
    def __init__(self, client: anthropic.Anthropic | None = None, cache: Cache | None = None):
        self._client = client
        self.cache = cache
        self.model = settings.anthropic_model
        # Token totals for cost reporting (eval/run_eval.py). Fit scoring calls from threads.
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
        self._usage_lock = threading.Lock()

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
        with self._usage_lock:
            self.usage["calls"] += 1
            self.usage["input_tokens"] += message.usage.input_tokens
            self.usage["output_tokens"] += message.usage.output_tokens
        if message.stop_reason in ("max_tokens", "refusal"):
            raise LLMError(f"model stopped early: {message.stop_reason}")
        return "".join(block.text for block in message.content if block.type == "text")

    def complete(
        self,
        system: str,
        inputs: dict | str,
        schema: type[T],
        profile_id: str | None = None,
        check: Callable[[T], None] | None = None,
    ) -> T:
        """One agent call: JSON in, validated `schema` out. A parse or validation failure is
        retried once with the error, then raised (CLAUDE.md rule 3).

        `check` is for rules that need more than the output itself, such as "every evidence
        id exists in this profile". It raises ValueError, which is treated like a schema
        failure. Its message goes to the model and to logs, so it must name positions, not
        content."""
        user = inputs if isinstance(inputs, str) else json.dumps(inputs, sort_keys=True)
        key = hashlib.sha256(f"{self.model}\0{system}\0{user}".encode()).hexdigest()
        if self.cache and (hit := self.cache.get(key)) is not None:
            return schema.model_validate_json(hit)

        messages = [{"role": "user", "content": user}]
        for attempt in (1, 2):
            raw = self._raw(system, messages)
            try:
                result = schema.model_validate(json.loads(repair_json(raw)))
                if check:
                    check(result)
            except (ValidationError, json.JSONDecodeError, ValueError) as e:
                problems = _problems(e)
                if attempt == 2:
                    raise LLMError(f"{schema.__name__} invalid after retry: {problems}") from None
                messages += [
                    {"role": "assistant", "content": raw},
                    {
                        "role": "user",
                        "content": f"Your output failed validation: {problems} "
                        "Return the corrected JSON only.",
                    },
                ]
                continue
            if self.cache:
                self.cache.set(key, result.model_dump_json(), profile_id)
            return result
        raise AssertionError("unreachable")
