"""Strict contracts for natural-language requirement interpretation."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from pae.domain.enums import DataType, TransformationKind, ValidationKind, ValidationSeverity
from pae.domain.models import ParameterValue, StrictModel


class AvailableField(StrictModel):
    """A confirmed field descriptor; source row values are intentionally excluded."""

    name: str = Field(min_length=1)
    data_type: DataType


class RequirementRequest(StrictModel):
    """Safe model input containing intent and metadata, never source samples."""

    requirement: str = Field(min_length=1, max_length=4_000)
    available_fields: tuple[AvailableField, ...] = Field(min_length=1)
    language_hint: Literal["th", "en", "mixed", "auto"] = "auto"

    @model_validator(mode="after")
    def field_names_are_unique(self) -> RequirementRequest:
        names = [field.name for field in self.available_fields]
        if len(names) != len(set(names)):
            raise ValueError("available field names must be unique")
        return self


class TransformationDraft(StrictModel):
    """One unconfirmed transformation proposed by the model."""

    rule_id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_-]*$")
    order: int = Field(ge=1)
    kind: TransformationKind
    inputs: tuple[str, ...] = Field(min_length=1)
    output: str | None
    parameters: dict[str, ParameterValue]


class ValidationDraft(StrictModel):
    rule_id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_-]*$")
    field: str = Field(min_length=1)
    kind: ValidationKind
    severity: ValidationSeverity = ValidationSeverity.ERROR
    parameters: dict[str, ParameterValue] = Field(default_factory=dict)


class RequirementAnalysis(StrictModel):
    """Schema-validated AI result which still requires user confirmation."""

    schema_version: Literal["1.0"]
    status: Literal["ready", "needs_clarification", "rejected"]
    transformations: tuple[TransformationDraft, ...]
    validations: tuple[ValidationDraft, ...] = ()
    confidence: float = Field(ge=0, le=1)
    warnings: tuple[str, ...]
    assumptions: tuple[str, ...] = ()
    clarification_questions: tuple[str, ...]

    @model_validator(mode="after")
    def status_is_consistent(self) -> RequirementAnalysis:
        if self.status == "ready" and not self.transformations:
            raise ValueError("ready output must contain at least one transformation")
        if self.status == "ready" and self.confidence < 0.75:
            raise ValueError("ready output must have confidence of at least 0.75")
        if self.status == "needs_clarification" and not self.clarification_questions:
            raise ValueError("needs_clarification output must contain a question")
        if self.status != "ready" and self.confidence >= 0.75:
            raise ValueError("non-ready output must have confidence below 0.75")
        if self.status != "ready" and (self.transformations or self.validations):
            raise ValueError("non-ready output may not contain rules")
        orders = [rule.order for rule in self.transformations]
        if len(orders) != len(set(orders)):
            raise ValueError("transformation order values must be unique")
        rule_ids = [rule.rule_id for rule in self.transformations]
        rule_ids.extend(rule.rule_id for rule in self.validations)
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("rule_id values must be unique")
        return self
