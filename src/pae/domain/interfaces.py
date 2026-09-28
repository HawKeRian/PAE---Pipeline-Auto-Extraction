"""Ports implemented by infrastructure connectors and code generators."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from pae.domain.enums import OutputFormat, SqlDialect, TargetLanguage, TransformationKind
from pae.domain.models import PipelineSpecification, SourceConfiguration

Scalar = str | int | float | bool | None


@dataclass(frozen=True)
class SourceSample:
    """Bounded, masked sample returned by a source connector."""

    source_fingerprint: str
    rows: tuple[Mapping[str, Scalar], ...]
    truncated: bool


@dataclass(frozen=True)
class GeneratedFile:
    """One generated text artifact with a repository-relative path."""

    path: str
    content: str


@dataclass(frozen=True)
class GeneratedBundle:
    """Code-generator output before validation and packaging."""

    files: tuple[GeneratedFile, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class GeneratorCapabilities:
    language: TargetLanguage
    dialect: SqlDialect | None
    transformations: frozenset[TransformationKind]
    outputs: frozenset[OutputFormat]


class SourceConnector(Protocol):
    """A read-only adapter for one source kind."""

    async def test_connection(self, source: SourceConfiguration) -> None: ...

    async def sample(self, source: SourceConfiguration) -> SourceSample: ...


class CodeGenerator(Protocol):
    """A deterministic generator for a target runtime."""

    @property
    def capabilities(self) -> GeneratorCapabilities: ...

    def generate(self, specification: PipelineSpecification) -> GeneratedBundle: ...
