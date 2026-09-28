"""Stable application errors shared by persistence and API layers."""

from __future__ import annotations

from typing import Any


class ApplicationError(RuntimeError):
    """Expected error safe to map to the public error envelope."""

    code = "APPLICATION_ERROR"
    status_code = 400
    retryable = False

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AuthenticationRequired(ApplicationError):
    code = "AUTHENTICATION_REQUIRED"
    status_code = 401


class ResourceNotFound(ApplicationError):
    code = "RESOURCE_NOT_FOUND"
    status_code = 404


class PermissionDenied(ApplicationError):
    code = "PERMISSION_DENIED"
    status_code = 403


class RevisionConflict(ApplicationError):
    code = "REVISION_CONFLICT"
    status_code = 409


class InvalidStateTransition(ApplicationError):
    code = "INVALID_STATE_TRANSITION"
    status_code = 409


class SecretValueRejected(ApplicationError):
    code = "SECRET_VALUE_REJECTED"
    status_code = 422


class CapacityLimit(ApplicationError):
    code = "CAPACITY_LIMIT"
    status_code = 429
    retryable = True


class RateLimitExceeded(ApplicationError):
    code = "RATE_LIMIT_EXCEEDED"
    status_code = 429
    retryable = True


class UploadTooLarge(ApplicationError):
    code = "UPLOAD_TOO_LARGE"
    status_code = 413


class FileTypeUnsupported(ApplicationError):
    code = "FILE_TYPE_UNSUPPORTED"
    status_code = 415


class FileContentInvalid(ApplicationError):
    code = "FILE_CONTENT_INVALID"
    status_code = 422


class UnsafeUpload(ApplicationError):
    code = "UNSAFE_UPLOAD"
    status_code = 422


class IngestionLimitExceeded(ApplicationError):
    code = "INGESTION_LIMIT_EXCEEDED"
    status_code = 422


class SheetSelectionRequired(ApplicationError):
    code = "SHEET_SELECTION_REQUIRED"
    status_code = 422


class EncodingInvalid(ApplicationError):
    code = "ENCODING_INVALID"
    status_code = 422


class SecretReferenceUnavailable(ApplicationError):
    code = "SECRET_REFERENCE_UNAVAILABLE"
    status_code = 422


class DatabaseHostRejected(ApplicationError):
    code = "DATABASE_HOST_REJECTED"
    status_code = 422


class UnsafeDatabaseQuery(ApplicationError):
    code = "UNSAFE_DATABASE_QUERY"
    status_code = 422


class DatabaseConnectionFailed(ApplicationError):
    code = "DATABASE_CONNECTION_FAILED"
    status_code = 422


class DatabaseReadOnlyRequired(ApplicationError):
    code = "DATABASE_READ_ONLY_REQUIRED"
    status_code = 422


class DatabaseQueryTimeout(ApplicationError):
    code = "DATABASE_QUERY_TIMEOUT"
    status_code = 408
    retryable = True


class UnsupportedCapability(ApplicationError):
    code = "UNSUPPORTED_CAPABILITY"
    status_code = 422


class ConfirmationRequired(ApplicationError):
    code = "CONFIRMATION_REQUIRED"
    status_code = 409


class InvalidSpecificationRule(ApplicationError):
    code = "INVALID_SPECIFICATION_RULE"
    status_code = 422


class SchemaChanged(ApplicationError):
    code = "SCHEMA_CHANGED"
    status_code = 409


class SandboxTimeout(ApplicationError):
    code = "SANDBOX_TIMEOUT"
    status_code = 408
    retryable = True


class SandboxResourceLimit(ApplicationError):
    code = "SANDBOX_RESOURCE_LIMIT"
    status_code = 422


class SandboxExecutionFailed(ApplicationError):
    code = "SANDBOX_EXECUTION_FAILED"
    status_code = 422
