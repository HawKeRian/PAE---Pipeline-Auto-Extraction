"""Normalized file metadata and reusable runtime suggestions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from pae.domain.enums import DataType, SchemaCompatibilityPolicy
from pae.domain.models import StrictModel

FileFormat = Literal["csv", "json", "json_lines", "excel", "parquet"]


class IngestionOptions(StrictModel):
    encoding: str | None = None
    delimiter: str | None = None
    sheet_name: str | None = None
    filename_pattern: str | None = None
    recursive: bool = False
    sample_row_limit: int = Field(default=10_000, ge=1, le=100_000)

    @field_validator("delimiter")
    @classmethod
    def delimiter_is_one_character(cls, value: str | None) -> str | None:
        if value is not None and len(value) != 1:
            raise ValueError("delimiter must contain exactly one character")
        return value


class ColumnProfile(StrictModel):
    name: str = Field(min_length=1)
    inferred_type: DataType
    required: bool
    nullable: bool
    present_percentage: float = Field(ge=0, le=100)


class RuntimeSuggestion(StrictModel):
    mode: Literal["folder_batch"] = "folder_batch"
    filename_pattern: str
    recursive: bool
    schema_policy: SchemaCompatibilityPolicy = SchemaCompatibilityPolicy.STRICT
    required_columns: tuple[str, ...]
    optional_columns: tuple[str, ...]


class NormalizedFileMetadata(StrictModel):
    original_name: str
    file_format: FileFormat
    content_type: str
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    encoding: str | None = None
    delimiter: str | None = None
    sheet_name: str | None = None
    available_sheets: tuple[str, ...] = ()
    sampled_rows: int = Field(ge=0)
    total_rows: int | None = Field(default=None, ge=0)
    truncated: bool
    columns: tuple[ColumnProfile, ...] = Field(min_length=1)


class IngestionAnalysis(StrictModel):
    metadata: NormalizedFileMetadata
    runtime: RuntimeSuggestion
    warnings: tuple[str, ...] = ()


class StoredIngestion(StrictModel):
    analysis: IngestionAnalysis
    storage_ref: str
    expires_at: datetime
    sample_rows: tuple[dict[str, Any], ...] = Field(exclude=True)
