"""Generated package and validation-stage models."""

from __future__ import annotations

from typing import Literal

from pae.domain.enums import ArtifactStatus, SqlDialect
from pae.domain.models import StrictModel


class GeneratedPackage(StrictModel):
    status: Literal[ArtifactStatus.GENERATED] = ArtifactStatus.GENERATED
    files: dict[str, str]
    checksum: str


class PackageValidation(StrictModel):
    status: ArtifactStatus
    syntax_valid: bool
    sample_matches_preview: bool
    checked_files: tuple[str, ...]


class GeneratedSqlPackage(StrictModel):
    status: Literal[ArtifactStatus.GENERATED] = ArtifactStatus.GENERATED
    dialect: SqlDialect
    files: dict[str, str]
    parameters: dict[str, object]
    checksum: str
