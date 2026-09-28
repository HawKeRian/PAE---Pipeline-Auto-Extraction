"""Safe fallback used when local inference cannot produce a trusted result."""

from pae.ai.models import RequirementAnalysis, RequirementRequest
from pae.ai.provider import AIProviderResult


class ClarificationFallbackProvider:
    """Never guesses transformations; asks the user to retry or clarify."""

    async def analyze(self, request: RequirementRequest) -> AIProviderResult:
        del request
        return AIProviderResult(
            analysis=RequirementAnalysis(
                schema_version="1.0",
                status="needs_clarification",
                transformations=(),
                confidence=0,
                warnings=("Local AI could not return a validated result.",),
                clarification_questions=(
                    "Please confirm the fields and describe the transformation more specifically.",
                ),
            ),
            model="safe-clarification-fallback",
        )
