"""Safe public contracts for database connection and sampling."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator, model_validator

from pae.domain.models import StrictModel

DatabaseType = Literal["postgresql", "mysql", "sql_server"]
ObjectType = Literal["table", "view"]
TlsMode = Literal["require", "verify_ca", "verify_identity"]


class DatabaseConnectionConfig(StrictModel):
    database_type: DatabaseType
    host: str = Field(min_length=1, max_length=253)
    port: int = Field(ge=1, le=65_535)
    database: str = Field(min_length=1, max_length=128)
    username: str = Field(min_length=1, max_length=128)
    connection_ref: str = Field(pattern=r"^secret://[A-Za-z0-9][A-Za-z0-9/_-]*$")
    tls_mode: TlsMode = "verify_identity"

    @field_validator("host")
    @classmethod
    def host_has_no_connection_string_tokens(cls, value: str) -> str:
        if any(token in value for token in (";", "=", "/", "\\", "@")):
            raise ValueError("host must be a hostname or IP address, not a connection string")
        return value.lower()

    @field_validator("database", "username")
    @classmethod
    def connection_values_are_not_fragments(cls, value: str) -> str:
        if any(token in value for token in (";", "{", "}")):
            raise ValueError("connection fields may not contain connection-string delimiters")
        return value

    def safe_summary(self) -> dict[str, Any]:
        """Return metadata safe for API responses and application logs."""

        return {
            "database_type": self.database_type,
            "host": "***",
            "port": self.port,
            "database": "***",
            "username": "***",
            "connection_ref": "secret://***",
            "tls_mode": self.tls_mode,
        }


class DatabaseCredential(StrictModel):
    password: SecretStr


class DatabaseSampleRequest(StrictModel):
    connection: DatabaseConnectionConfig
    schema_name: str | None = Field(default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_$]*$")
    object_name: str | None = Field(default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_$]*$")
    read_only_query: str | None = Field(default=None, min_length=1, max_length=100_000)
    sample_limit: int = Field(default=10_000, ge=1, le=100_000)
    timeout_seconds: int = Field(default=30, ge=1, le=300)

    @model_validator(mode="after")
    def one_source_target(self) -> DatabaseSampleRequest:
        if bool(self.object_name) == bool(self.read_only_query):
            raise ValueError("exactly one of object_name or read_only_query is required")
        return self


class DatabaseObject(StrictModel):
    schema_name: str
    object_name: str
    object_type: ObjectType


class DatabaseCatalog(StrictModel):
    schemas: tuple[str, ...]
    objects: tuple[DatabaseObject, ...]


class DatabaseSample(StrictModel):
    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    truncated: bool
    source: dict[str, Any]


class QueryResult(StrictModel):
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
