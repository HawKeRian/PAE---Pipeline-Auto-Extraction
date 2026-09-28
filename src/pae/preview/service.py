"""Preview orchestration using the same runtime core copied into generated Python."""

from __future__ import annotations

from typing import Any

from pae.domain.enums import PiiClassification
from pae.domain.models import PipelineSpecification
from pae.persistence.errors import SchemaChanged
from pae.preview.models import PreviewResult, RejectedRecord
from pae.sandbox import SandboxRunner


class PreviewService:
    def __init__(self, sandbox: SandboxRunner) -> None:
        self.sandbox = sandbox

    @staticmethod
    def _mask_row(row: dict[str, Any], sensitive: set[str]) -> dict[str, Any]:
        return {
            key: ("***" if key in sensitive and value is not None else value)
            for key, value in row.items()
        }

    async def preview(
        self,
        specification: PipelineSpecification,
        rows: tuple[dict[str, Any], ...],
        *,
        timeout_seconds: float | None = None,
    ) -> PreviewResult:
        expected = {field.source_name for field in specification.fields if field.selected}
        required = {
            field.source_name for field in specification.fields if field.selected and field.required
        }
        actual = {name for row in rows for name in row}
        missing = required - actual
        extra = actual - expected
        source = specification.sources[0]
        strict_extra = (
            source.kind == "file" and source.runtime.schema_policy.value == "strict" and bool(extra)
        )
        if missing or strict_extra:
            impacted = sorted(
                rule.rule_id for rule in specification.transformations if set(rule.inputs) & missing
            )
            impacted.extend(
                rule.rule_id for rule in specification.validations if rule.field in missing
            )
            raise SchemaChanged(
                "The sample schema is missing confirmed required fields.",
                details={
                    "missing_fields": sorted(missing),
                    "extra_fields": sorted(extra),
                    "impacted_rules": sorted(set(impacted)),
                },
            )
        result = await self.sandbox.run(
            {
                "operation": "preview",
                "specification": specification.model_dump(mode="json"),
                "rows": list(rows),
            },
            timeout_seconds=timeout_seconds,
        )
        sensitive = {
            name
            for field in specification.fields
            if field.pii_classification is not PiiClassification.NONE
            for name in (field.source_name, field.target_name)
        }
        before = tuple(self._mask_row(dict(row), sensitive) for row in rows)
        after = tuple(self._mask_row(dict(row), sensitive) for row in result["output_rows"])
        rejected = tuple(
            RejectedRecord.model_validate(
                {**item, "row": self._mask_row(dict(item["row"]), sensitive)}
            )
            for item in result["rejected_rows"]
        )
        issues = result["issues"]
        return PreviewResult(
            before_rows=before,
            after_rows=after,
            rejected_rows=rejected,
            errors=tuple(item for item in issues if item["severity"] == "error"),
            warnings=tuple(item for item in issues if item["severity"] == "warning"),
            rule_impacts=tuple(result["rule_impacts"]),
            input_count=result["input_count"],
            output_count=result["output_count"],
            rejected_count=result["rejected_count"],
        )
