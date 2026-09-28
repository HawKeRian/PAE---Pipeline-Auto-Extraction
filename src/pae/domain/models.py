"""Versioned, strict domain models for Pipeline Auto Extraction."""

from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pae.domain.enums import (
    ArtifactStatus,
    DataType,
    ErrorPolicy,
    FileFailurePolicy,
    JobStatus,
    OutputFormat,
    PiiClassification,
    ProcessedFileTracking,
    ProjectStatus,
    SchemaCompatibilityPolicy,
    SqlDialect,
    TargetLanguage,
    TransformationKind,
    ValidationKind,
    ValidationSeverity,
    WriteMode,
)

ParameterValue = str | int | float | bool | None | list[str] | list[int] | dict[str, str]


class StrictModel(BaseModel):
    """Reject unknown fields so stale or unsafe input cannot pass silently."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class FileDiscoveryContract(StrictModel):
    """Reusable runtime contract for discovering future files in a folder."""

    mode: Literal["folder_batch"] = "folder_batch"
    input_directory_parameter: str = "input_dir"
    filename_pattern: str = Field(min_length=1, default="*.csv")
    recursive: bool = False
    discovery_order: Literal["path_ascending"] = "path_ascending"
    schema_policy: SchemaCompatibilityPolicy = SchemaCompatibilityPolicy.STRICT
    failure_policy: FileFailurePolicy = FileFailurePolicy.QUARANTINE
    processed_tracking: ProcessedFileTracking = ProcessedFileTracking.MANIFEST
    processed_manifest_parameter: str = "state_file"
    quarantine_directory_parameter: str = "quarantine_dir"
    archive_directory_parameter: str | None = None

    @model_validator(mode="after")
    def pattern_is_relative_and_bounded(self) -> FileDiscoveryContract:
        normalized = self.filename_pattern.replace("\\", "/")
        path = PurePosixPath(normalized)
        if normalized.startswith("/") or ":" in normalized or ".." in path.parts:
            raise ValueError("filename_pattern must be a relative glob without parent traversal")
        if "**" in path.parts and not self.recursive:
            raise ValueError("recursive must be true when filename_pattern contains **")
        return self


class FileSource(StrictModel):
    kind: Literal["file"] = "file"
    source_id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_-]*$")
    file_format: Literal["csv", "json", "json_lines", "excel", "parquet"]
    original_name: str = Field(min_length=1)
    sheet_name: str | None = None
    delimiter: str | None = Field(default=None, min_length=1, max_length=1)
    encoding: str = "utf-8"
    sample_limit: int = Field(default=100_000, ge=1, le=100_000)
    runtime: FileDiscoveryContract


class DatabaseSource(StrictModel):
    kind: Literal["database"] = "database"
    source_id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_-]*$")
    database_type: Literal["postgresql", "mysql", "sql_server"]
    connection_ref: str = Field(
        min_length=1,
        description="Reference to a secret-managed connection; never a password or connection URI.",
    )
    schema_name: str | None = None
    object_name: str | None = None
    read_only_query: str | None = None
    sample_limit: int = Field(default=10_000, ge=1, le=100_000)

    @model_validator(mode="after")
    def require_table_or_query(self) -> DatabaseSource:
        if bool(self.object_name) == bool(self.read_only_query):
            raise ValueError("exactly one of object_name or read_only_query is required")
        return self


SourceConfiguration = Annotated[FileSource | DatabaseSource, Field(discriminator="kind")]


class FieldDefinition(StrictModel):
    source_id: str
    source_name: str = Field(min_length=1)
    target_name: str = Field(min_length=1)
    inferred_type: DataType
    confirmed_type: DataType
    nullable: bool
    required: bool = True
    selected: bool = True
    confidence: float = Field(ge=0, le=1)
    null_percentage: float = Field(ge=0, le=100)
    distinct_count: int | None = Field(default=None, ge=0)
    pii_classification: PiiClassification = PiiClassification.NONE
    samples_masked: tuple[str, ...] = ()


class TransformationRule(StrictModel):
    rule_id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_-]*$")
    order: int = Field(ge=1)
    kind: TransformationKind
    inputs: tuple[str, ...] = Field(min_length=1)
    output: str | None = None
    parameters: dict[str, ParameterValue] = Field(default_factory=dict)
    enabled: bool = True


class ValidationRule(StrictModel):
    rule_id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_-]*$")
    field: str = Field(min_length=1)
    kind: ValidationKind
    severity: ValidationSeverity = ValidationSeverity.ERROR
    parameters: dict[str, ParameterValue] = Field(default_factory=dict)


class JoinDefinition(StrictModel):
    join_id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_-]*$")
    left_source_id: str
    right_source_id: str
    join_type: Literal["inner", "left", "right", "full"]
    left_keys: tuple[str, ...] = Field(min_length=1)
    right_keys: tuple[str, ...] = Field(min_length=1)
    expected_cardinality: Literal["one_to_one", "one_to_many", "many_to_one", "many_to_many"]
    duplicate_column_policy: Literal["prefix_source", "reject"] = "reject"

    @model_validator(mode="after")
    def keys_have_matching_arity(self) -> JoinDefinition:
        if len(self.left_keys) != len(self.right_keys):
            raise ValueError("left_keys and right_keys must have the same length")
        if self.left_source_id == self.right_source_id:
            raise ValueError("a join must reference two different sources")
        return self


class OutputContract(StrictModel):
    format: OutputFormat
    destination: Literal["artifact"] = "artifact"
    output_directory_parameter: str = "output_dir"
    path_template: str = Field(min_length=1, default="output/result")
    encoding: Literal["utf-8"] = "utf-8"
    null_representation: str = ""
    write_mode: WriteMode = WriteMode.OVERWRITE
    atomic_write: bool = True


class TargetRuntime(StrictModel):
    language: TargetLanguage
    sql_dialect: SqlDialect | None = None

    @model_validator(mode="after")
    def dialect_matches_language(self) -> TargetRuntime:
        if self.language is TargetLanguage.SQL and self.sql_dialect is None:
            raise ValueError("sql_dialect is required for SQL targets")
        if self.language is not TargetLanguage.SQL and self.sql_dialect is not None:
            raise ValueError("sql_dialect is valid only for SQL targets")
        return self


class PipelineSpecification(StrictModel):
    specification_version: Literal["1.0"] = "1.0"
    specification_id: UUID
    project_id: UUID
    revision: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=120)
    source_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    sources: tuple[SourceConfiguration, ...] = Field(min_length=1)
    fields: tuple[FieldDefinition, ...] = Field(min_length=1)
    transformations: tuple[TransformationRule, ...] = ()
    validations: tuple[ValidationRule, ...] = ()
    joins: tuple[JoinDefinition, ...] = ()
    error_policy: ErrorPolicy = ErrorPolicy.REJECT_RECORD
    output: OutputContract
    target: TargetRuntime
    confirmed_by: str = Field(min_length=1)
    confirmed_at: datetime

    @model_validator(mode="after")
    def validate_references_and_order(self) -> PipelineSpecification:
        source_ids = [source.source_id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source_id values must be unique")

        unknown_sources = {field.source_id for field in self.fields} - set(source_ids)
        if unknown_sources:
            raise ValueError(f"fields reference unknown sources: {sorted(unknown_sources)}")

        selected_fields = [field for field in self.fields if field.selected]
        target_names = [field.target_name for field in selected_fields]
        if len(target_names) != len(set(target_names)):
            raise ValueError("selected target_name values must be unique")

        field_references = {
            name for field in selected_fields for name in (field.source_name, field.target_name)
        }
        unknown_rule_fields = {
            field
            for rule in self.transformations
            for field in rule.inputs
            if field not in field_references
        }
        if unknown_rule_fields:
            raise ValueError(
                f"transformations reference unknown selected fields: {sorted(unknown_rule_fields)}"
            )

        rule_orders = [rule.order for rule in self.transformations]
        if len(rule_orders) != len(set(rule_orders)):
            raise ValueError("transformation order values must be unique")

        unknown_validation_fields = {
            rule.field for rule in self.validations if rule.field not in field_references
        }
        if unknown_validation_fields:
            unknown_names = sorted(unknown_validation_fields)
            raise ValueError(f"validations reference unknown selected fields: {unknown_names}")

        field_sources = {
            (field.source_id, field.source_name) for field in self.fields if field.selected
        }
        for join in self.joins:
            if join.left_source_id not in source_ids or join.right_source_id not in source_ids:
                raise ValueError(f"join {join.join_id} references an unknown source")
            for source_id, key in (
                *((join.left_source_id, key) for key in join.left_keys),
                *((join.right_source_id, key) for key in join.right_keys),
            ):
                if (source_id, key) not in field_sources:
                    field_reference = f"{source_id}.{key}"
                    raise ValueError(
                        f"join {join.join_id} references unknown key {field_reference}"
                    )

        if self.confirmed_at.utcoffset() is None:
            raise ValueError("confirmed_at must include a timezone")
        return self


class ProjectRecord(StrictModel):
    project_id: UUID
    owner_id: str
    name: str
    status: ProjectStatus
    current_revision: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class RevisionIdentity(StrictModel):
    source_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    schema_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    specification_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    generator_version: str
    model_version: str | None = None


class GenerationJob(StrictModel):
    job_id: UUID
    project_id: UUID
    revision: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1)
    status: JobStatus
    progress_percentage: int = Field(ge=0, le=100)
    attempt: int = Field(default=1, ge=1)
    revision_identity: RevisionIdentity
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None


class ArtifactManifest(StrictModel):
    artifact_id: UUID
    project_id: UUID
    revision: int = Field(ge=1)
    status: ArtifactStatus
    revision_identity: RevisionIdentity
    files: tuple[str, ...] = Field(min_length=1)
    contains_credentials: Literal[False] = False
    contains_source_sample: Literal[False] = False
    created_at: datetime
