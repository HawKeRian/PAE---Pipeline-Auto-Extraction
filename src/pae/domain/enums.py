"""Stable enumerations used by the versioned Pipeline Specification."""

from enum import StrEnum


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    SOURCE_READY = "source_ready"
    ANALYZED = "analyzed"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DataType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    JSON = "json"


class PiiClassification(StrEnum):
    NONE = "none"
    POSSIBLE = "possible"
    CONFIRMED = "confirmed"


class TransformationKind(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"
    RENAME = "rename"
    CAST = "cast"
    FILTER = "filter"
    SORT = "sort"
    DEDUPLICATE = "deduplicate"
    REPLACE = "replace"
    HANDLE_NULL = "handle_null"
    DERIVE = "derive"
    AGGREGATE = "aggregate"
    MASK = "mask"
    JOIN = "join"


class ValidationKind(StrEnum):
    NOT_NULL = "not_null"
    UNIQUE = "unique"
    RANGE = "range"
    REGEX = "regex"
    ALLOWED_VALUES = "allowed_values"


class ValidationSeverity(StrEnum):
    WARNING = "warning"
    ERROR = "error"


class ErrorPolicy(StrEnum):
    REJECT_RECORD = "reject_record"
    FAIL_JOB = "fail_job"


class OutputFormat(StrEnum):
    CSV = "csv"
    JSON_LINES = "json_lines"
    PARQUET = "parquet"
    SQL_RESULT = "sql_result"


class WriteMode(StrEnum):
    OVERWRITE = "overwrite"
    APPEND = "append"


class SchemaCompatibilityPolicy(StrEnum):
    STRICT = "strict"
    ALLOW_EXTRA_COLUMNS = "allow_extra_columns"


class FileFailurePolicy(StrEnum):
    FAIL_BATCH = "fail_batch"
    QUARANTINE = "quarantine"
    SKIP = "skip"


class ProcessedFileTracking(StrEnum):
    MANIFEST = "manifest"
    ARCHIVE = "archive"


class TargetLanguage(StrEnum):
    PYTHON = "python"
    SQL = "sql"
    JAVASCRIPT = "javascript"


class SqlDialect(StrEnum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQL_SERVER = "sql_server"


class ArtifactStatus(StrEnum):
    GENERATED = "generated"
    SYNTAX_VALIDATED = "syntax_validated"
    SAMPLE_TESTED = "sample_tested"
    USER_APPROVED = "user_approved"
    PRODUCTION_REVIEWED = "production_reviewed"
