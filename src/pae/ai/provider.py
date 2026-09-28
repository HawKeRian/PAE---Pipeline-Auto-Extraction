"""Runtime-neutral AI provider contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pae.ai.models import RequirementAnalysis, RequirementRequest


class AIProviderError(RuntimeError):
    """Base exception for a provider failure safe to handle with a fallback."""


class AIProviderUnavailable(AIProviderError):
    """The local runtime or configured model is unavailable."""


class AIOutputInvalid(AIProviderError):
    """The model returned content which violates the output contract."""


@dataclass(frozen=True)
class InferenceMetrics:
    """Non-sensitive runtime measurements returned by a provider."""

    total_seconds: float | None = None
    load_seconds: float | None = None
    prompt_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class AIProviderResult:
    analysis: RequirementAnalysis
    model: str
    metrics: InferenceMetrics = InferenceMetrics()


class AIProvider(Protocol):
    """Port allowing the runtime/model to change without business-logic changes."""

    async def analyze(self, request: RequirementRequest) -> AIProviderResult: ...
