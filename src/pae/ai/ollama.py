"""Ollama implementation of the local AI provider."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import ValidationError

from pae.ai.models import RequirementAnalysis, RequirementRequest
from pae.ai.prompt import SYSTEM_PROMPT, build_user_prompt
from pae.ai.provider import (
    AIOutputInvalid,
    AIProviderResult,
    AIProviderUnavailable,
    InferenceMetrics,
)


class OllamaProvider:
    """Call a local Ollama server with JSON Schema constrained decoding."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float = 120,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds
        self._transport = transport

    async def analyze(self, request: RequirementRequest) -> AIProviderResult:
        payload = {
            "model": self._model,
            "stream": False,
            "format": RequirementAnalysis.model_json_schema(),
            "options": {"temperature": 0, "num_ctx": 4096},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(request)},
            ],
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.post(f"{self._base_url}/api/chat", json=payload)
                response.raise_for_status()
                body: dict[str, Any] = response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise AIProviderUnavailable(f"local Ollama rejected the request: {detail}") from exc
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise AIProviderUnavailable("local Ollama inference is unavailable") from exc

        try:
            content = body["message"]["content"]
            analysis = RequirementAnalysis.model_validate_json(content)
        except ValidationError as exc:
            errors = exc.errors(include_input=False, include_url=False)
            raise AIOutputInvalid(f"model output failed schema validation: {errors}") from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise AIOutputInvalid("model output was not a valid response object") from exc

        return AIProviderResult(
            analysis=analysis,
            model=body.get("model", self._model),
            metrics=InferenceMetrics(
                total_seconds=_nanoseconds_to_seconds(body.get("total_duration")),
                load_seconds=_nanoseconds_to_seconds(body.get("load_duration")),
                prompt_tokens=_optional_int(body.get("prompt_eval_count")),
                output_tokens=_optional_int(body.get("eval_count")),
            ),
        )


def _nanoseconds_to_seconds(value: object) -> float | None:
    return value / 1_000_000_000 if isinstance(value, int | float) else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None
