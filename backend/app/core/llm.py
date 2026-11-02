import hashlib
import json
import logging
import re
import threading
import time
from collections.abc import Callable
from typing import Protocol, TypeVar

import anthropic
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import BaseModel, ValidationError

from app.core.config import settings

log = logging.getLogger("careerpilot.llm")

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Raised when the model cannot produce valid output. Never carries prompt or response
    text, because those hold resume content (CLAUDE.md rule 6)."""


class QuotaExhausted(LLMError):
    """This model has no quota left for now. Gemini counts quota per model, so another
    configured model may still answer; when none is left this surfaces as the LLMError it
    is."""


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


GOOGLE_ATTEMPTS = 6


def _retry_delay(e: Exception, attempt: int) -> float:
    """Seconds to wait before retrying a rate-limited Gemini call: what the server asked for
    ("Please retry in 12.5s") plus a second, else exponential.

    A wait of more than two minutes means the daily quota is gone, not the per-minute one.
    Retrying cannot help and each attempt is refused anyway, so that fails at once."""
    # The delay arrives as a RetryInfo detail ("retryDelay": "24337s") and usually also in
    # the message text; the JSON is searched as text so either place is found.
    body = json.dumps(getattr(e, "details", None), default=str) + (
        getattr(e, "message", None) or ""
    )
    asked = re.search(r'retryDelay": "([\d.]+)s|retry in ([\d.]+)s', body)
    if not asked:
        return min(60.0, 2.0**attempt)
    seconds = float(asked.group(1) or asked.group(2))
    if seconds > 120:
        raise QuotaExhausted(
            f"Gemini daily quota used up for this model; resets in {seconds / 3600:.1f} h"
        )
    return seconds + 1


def _problems(e: Exception) -> str:
    if isinstance(e, ValidationError):
        return json.dumps(e.errors(include_input=False, include_url=False), default=str)
    if isinstance(e, json.JSONDecodeError):
        return f"invalid JSON: {e.msg} at line {e.lineno} column {e.colno}"
    return str(e)  # a ValueError raised by an agent's check


class LLM:
    """One model behind every agent. LLM_PROVIDER picks Anthropic (the default the prompts
    were written for) or Google Gemini; everything above `_raw` is provider-neutral."""

    def __init__(self, client=None, cache: Cache | None = None, client_factory=None):
        self._client = client
        self._custom_client = client is not None
        self._client_factory = client_factory
        self.cache = cache
        self.provider = settings.llm_provider
        if self.provider == "google":
            self.models = settings.google_models
        elif self.provider == "openrouter":
            self.models = [settings.openrouter_model]
        elif self.provider == "deepseek":
            self.models = [settings.deepseek_model]
        else:
            self.models = [settings.anthropic_model]
        self.model = self.models[0]
        self.google_keys = settings.google_api_keys
        self.google_key_index = 0
        self.anthropic_keys = settings.anthropic_api_keys
        self.anthropic_key_index = 0
        # Token totals for cost reporting (eval/run_eval.py). Fit scoring calls from threads.
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
        self._usage_lock = threading.Lock()

    def _raw(self, system: str, messages: list[dict]) -> str:
        if self.provider == "google":
            call = self._google
        elif self.provider == "openrouter":
            call = self._openrouter
        elif self.provider == "deepseek":
            call = self._deepseek
        else:
            call = self._anthropic
        text, tokens_in, tokens_out = call(system, messages)
        with self._usage_lock:
            self.usage["calls"] += 1
            self.usage["input_tokens"] += tokens_in
            self.usage["output_tokens"] += tokens_out
        return text

    def _openai_compatible(
        self, base_url: str, api_key: str, model: str, system: str, messages: list[dict]
    ) -> tuple[str, int, int]:
        import httpx2 as httpx

        if not api_key:
            raise LLMError(f"no API key configured for {self.provider}")
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}] + messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        try:
            resp = httpx.post(
                f"{base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            text = choice["message"]["content"]
            usage = data.get("usage", {})
            return text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
        except (
            httpx.HTTPStatusError,
            httpx.RequestError,
            KeyError,
            IndexError,
            json.JSONDecodeError,
        ) as e:
            raise LLMError(f"model call failed: {type(e).__name__}") from None

    def _openrouter(self, system: str, messages: list[dict]) -> tuple[str, int, int]:
        return self._openai_compatible(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key,
            model=self.model,
            system=system,
            messages=messages,
        )

    def _deepseek(self, system: str, messages: list[dict]) -> tuple[str, int, int]:
        return self._openai_compatible(
            base_url="https://api.deepseek.com/v1",
            api_key=settings.deepseek_api_key,
            model=self.model,
            system=system,
            messages=messages,
        )

    def _anthropic(self, system: str, messages: list[dict]) -> tuple[str, int, int]:
        if self._client is None:
            # api_key=None lets the SDK resolve credentials from the environment
            api_key = (
                self.anthropic_keys[self.anthropic_key_index]
                if self.anthropic_keys
                else (settings.anthropic_api_key or None)
            )
            self._client = anthropic.Anthropic(
                api_key=api_key, max_retries=3
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
        text = "".join(block.text for block in message.content if block.type == "text")
        return text, message.usage.input_tokens, message.usage.output_tokens

    def _make_google_client(self, key: str):
        if self._client_factory:
            return self._client_factory(key)
        return genai.Client(api_key=key)

    def _next_google_key(self) -> bool:
        """Switch to the next configured Google API key, if there is one."""
        if self.google_key_index + 1 < len(self.google_keys):
            self.google_key_index += 1
            log.warning(
                "Rotating to next Google API key (%d of %d)",
                self.google_key_index + 1,
                len(self.google_keys),
            )
            if not self._custom_client or self._client_factory:
                self._client = self._make_google_client(self.google_keys[self.google_key_index])
            return True
        return False

    def _next_model(self) -> bool:
        """Switch to the next configured model, if there is one. The switch sticks: a model
        that is out of quota for the day will not come back during this process."""
        later = self.models[self.models.index(self.model) + 1 :]
        if not later:
            return False
        log.warning("%s cannot be used, falling back to %s", self.model, later[0])
        self.model = later[0]
        if self.google_keys and (not self._custom_client or self._client_factory):
            self.google_key_index = 0
            self._client = self._make_google_client(self.google_keys[0])
        return True

    def _google(self, system: str, messages: list[dict]) -> tuple[str, int, int]:
        if self._client is None:
            if not self.google_keys:
                raise LLMError("no Google API key configured")
            self._client = self._make_google_client(self.google_keys[self.google_key_index])
        contents = [
            # Gemini calls the assistant turn "model"
            {
                "role": "model" if m["role"] == "assistant" else "user",
                "parts": [{"text": m["content"]}],
            }
            for m in messages
        ]
        config = genai_types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            max_output_tokens=32000,
        )
        for attempt in range(1, GOOGLE_ATTEMPTS + 1):
            try:
                response = self._client.models.generate_content(
                    model=self.model, contents=contents, config=config
                )
                break
            except genai_errors.APIError as e:
                # A name this key cannot use is worth skipping rather than failing on: the
                # chain is written by hand and one wrong id would otherwise stop every call
                # from that point on.
                if e.code == 404 and self._next_model():
                    continue
                # If an invalid key or permission issue occurs and another key is available, rotate
                if e.code in (400, 403) and self._next_google_key():
                    continue
                # 429 = rate limit (the free tier allows a few requests a minute), 503 = busy
                if e.code not in (429, 503) or attempt == GOOGLE_ATTEMPTS:
                    raise LLMError(f"model call failed: {type(e).__name__} {e.code}") from None
                try:
                    delay = _retry_delay(e, attempt)
                except QuotaExhausted:
                    if self._next_google_key():
                        continue  # next key has its own quota, try immediately
                    if self._next_model():
                        continue  # the next model has its own quota, so try it straight away
                    if not self._custom_client or getattr(self, "_allow_fallback", False):
                        if settings.deepseek_api_key:
                            log.warning("All Google keys and models exhausted; falling back to DeepSeek")
                            return self._openai_compatible(
                                base_url="https://api.deepseek.com/v1",
                                api_key=settings.deepseek_api_key,
                                model=settings.deepseek_model,
                                system=system,
                                messages=messages,
                            )
                        if settings.openrouter_api_key:
                            log.warning("All Google keys and models exhausted; falling back to OpenRouter")
                            return self._openai_compatible(
                                base_url="https://openrouter.ai/api/v1",
                                api_key=settings.openrouter_api_key,
                                model=settings.openrouter_model,
                                system=system,
                                messages=messages,
                            )
                    raise
                # If another key is available, try it before waiting on per-minute rate limit
                if self._next_google_key():
                    continue
                time.sleep(delay)
        reason = response.candidates[0].finish_reason if response.candidates else None
        if reason is None or reason.name != "STOP":
            raise LLMError(f"model stopped early: {reason.name if reason else 'no candidates'}")
        usage = response.usage_metadata
        tokens_out = (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)
        return response.text or "", usage.prompt_token_count or 0, tokens_out

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
