"""Validated requirement interpretation service."""

from __future__ import annotations

from pae.ai.models import RequirementRequest
from pae.ai.provider import AIProvider, AIProviderError, AIProviderResult


class RequirementInterpreter:
    """Validate model semantics and fall back instead of trusting invalid references."""

    def __init__(self, primary: AIProvider, fallback: AIProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    async def analyze(self, request: RequirementRequest) -> AIProviderResult:
        try:
            result = await self._primary.analyze(request)
            self._validate_references(request, result)
            return result
        except (AIProviderError, ValueError):
            return await self._fallback.analyze(request)

    @staticmethod
    def _validate_references(request: RequirementRequest, result: AIProviderResult) -> None:
        allowed = {field.name for field in request.available_fields}
        unknown = {
            field
            for rule in result.analysis.transformations
            for field in rule.inputs
            if field not in allowed
        }
        if unknown:
            raise ValueError(f"AI output references unknown fields: {sorted(unknown)}")
        unknown_validations = {
            rule.field for rule in result.analysis.validations if rule.field not in allowed
        }
        if unknown_validations:
            raise ValueError(
                f"AI validation output references unknown fields: {sorted(unknown_validations)}"
            )
