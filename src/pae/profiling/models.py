"""Contracts for inferred and user-confirmed schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from pae.domain.enums import DataType, PiiClassification
from pae.domain.models import StrictModel

SensitiveCategory = Literal[
    "email", "phone", "national_id", "credit_card", "ip_address", "identifier"
]


class ProfileField(StrictModel):
    name: str = Field(min_length=1)
    inferred_type: DataType
    observed_types: tuple[DataType, ...]
    mixed_types: bool
    nullable: bool
    required: bool
    null_count: int = Field(ge=0)
    null_percentage: float = Field(ge=0, le=100)
    distinct_count: int = Field(ge=0)
    minimum: str | int | float | None = None
    maximum: str | int | float | None = None
    detected_format: str | None = None
    samples_masked: tuple[str, ...] = ()
    confidence: float = Field(ge=0, le=1)
    pii_classification: PiiClassification = PiiClassification.NONE
    sensitive_category: SensitiveCategory | None = None


class ProfilingResult(StrictModel):
    row_count: int = Field(ge=0)
    sampled_rows: int = Field(ge=0)
    truncated: bool
    fields: tuple[ProfileField, ...]
    warnings: tuple[str, ...] = ()


class ConfirmedField(StrictModel):
    name: str = Field(min_length=1)
    inferred_type: DataType
    confirmed_type: DataType
    nullable: bool
    required: bool
    selected: bool = True
    confidence: float = Field(ge=0, le=1)
    null_percentage: float = Field(ge=0, le=100)
    distinct_count: int | None = Field(default=None, ge=0)
    pii_classification: PiiClassification = PiiClassification.NONE
    samples_masked: tuple[str, ...] = ()


class SchemaConfirmation(StrictModel):
    fields: tuple[ConfirmedField, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def field_names_are_unique(self) -> SchemaConfirmation:
        names = [field.name for field in self.fields]
        if len(names) != len(set(names)):
            raise ValueError("confirmed field names must be unique")
        return self


class ConfirmedSchema(StrictModel):
    project_id: str
    revision: int = Field(ge=1)
    fields: tuple[ConfirmedField, ...] = Field(min_length=1)
    schema_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirmed_by: str
    confirmed_at: datetime


class ProfilingRequest(StrictModel):
    rows: tuple[dict[str, Any], ...] = Field(min_length=1, max_length=100_000)
    total_rows: int | None = Field(default=None, ge=1)
    sample_limit: int = Field(default=10_000, ge=1, le=100_000)
