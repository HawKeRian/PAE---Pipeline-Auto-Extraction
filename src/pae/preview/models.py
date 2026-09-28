"""Public models for transformation preview results."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from pae.domain.models import StrictModel


class PreviewRequest(StrictModel):
    rows: tuple[dict[str, Any], ...] = Field(min_length=1, max_length=10_000)
    timeout_seconds: float = Field(default=5, gt=0, le=30)


class RuleImpact(StrictModel):
    rule_id: str
    kind: str
    before_count: int = Field(ge=0)
    after_count: int = Field(ge=0)
    changed_count: int = Field(ge=0)


class PreviewIssue(StrictModel):
    rule_id: str
    row_index: int = Field(ge=0)
    field: str
    severity: Literal["warning", "error"]
    message: str


class RejectedRecord(StrictModel):
    row_index: int = Field(ge=0)
    rule_id: str
    reason: str
    row: dict[str, Any]


class PreviewResult(StrictModel):
    status: Literal["sample_tested"] = "sample_tested"
    before_rows: tuple[dict[str, Any], ...]
    after_rows: tuple[dict[str, Any], ...]
    rejected_rows: tuple[RejectedRecord, ...]
    errors: tuple[PreviewIssue, ...]
    warnings: tuple[PreviewIssue, ...]
    rule_impacts: tuple[RuleImpact, ...]
    input_count: int = Field(ge=0)
    output_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    schema_compatible: Literal[True] = True
