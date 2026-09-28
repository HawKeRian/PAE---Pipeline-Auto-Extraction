"""Build, scan, store, and retrieve self-contained generated pipeline packages."""

# ruff: noqa: E501 -- generated README lines remain readable as complete user instructions.

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from pae import __version__
from pae.domain.enums import TargetLanguage
from pae.domain.models import PipelineSpecification
from pae.generation import JavaScriptGenerator, PythonGenerator, SqlGenerator
from pae.generation.models import GeneratedPackage, GeneratedSqlPackage, PackageValidation
from pae.persistence.errors import ResourceNotFound, SecretValueRejected
from pae.runtime_core import execute
from pae.sandbox import SandboxRunner

_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(
        r"(?i)(?:password|passwd|api[_-]?key|access[_-]?token)\s*[:=]\s*['\"]?[^\s'\"#]{8,}"
    ),
    re.compile(r"(?i)\b(?:postgres(?:ql)?|mysql|mssql)://[^\s/@:]+:[^\s/@]+@"),
)


@dataclass(frozen=True)
class ExportedPackage:
    """Package bytes and public metadata ready to persist."""

    content: bytes
    manifest: dict[str, Any]
    validation: dict[str, Any]
    checksum: str


class ArtifactExportService:
    """Create deterministic, path-safe archives without source samples or credentials."""

    def __init__(self, storage_root: Path, sandbox: SandboxRunner) -> None:
        self.storage_root = storage_root.resolve()
        self.sandbox = sandbox

    async def build(
        self,
        specification: PipelineSpecification,
        *,
        sample_rows: tuple[dict[str, Any], ...] = (),
        model_version: str | None = None,
    ) -> ExportedPackage:
        package, validation = await self._generate_and_validate(specification, sample_rows)
        files = dict(package.files)
        if "config.example.env" in files:
            files[".env.example"] = files.pop("config.example.env")
        files["pipeline-spec.json"] = (
            json.dumps(
                specification.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True
            )
            + "\n"
        )
        files["README.md"] = self._readme(specification, validation)
        files["sample-output.json"] = self._masked_sample_output(specification, sample_rows)
        self._validate_paths(files)
        self._scan(files)
        file_entries = [
            {
                "path": name,
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "size_bytes": len(content.encode("utf-8")),
            }
            for name, content in sorted(files.items())
        ]
        manifest: dict[str, Any] = {
            "artifact_format_version": "1.0",
            "project_id": str(specification.project_id),
            "specification_id": str(specification.specification_id),
            "revision": specification.revision,
            "source_fingerprint": specification.source_fingerprint,
            "generator_version": __version__,
            "model_version": model_version,
            "language": specification.target.language,
            "sql_dialect": specification.target.sql_dialect,
            "artifact_status": validation.status,
            "validation": validation.model_dump(mode="json"),
            "files": file_entries,
            "content_set_sha256": hashlib.sha256(
                json.dumps(file_entries, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            "contains_credentials": False,
            "contains_source_sample": False,
            "sample_output_masked": True,
            "generated_at": datetime.now(UTC).isoformat(),
        }
        files["artifact-manifest.json"] = (
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
        self._scan(files)
        content = self._archive(files)
        checksum = hashlib.sha256(content).hexdigest()
        manifest["package_sha256"] = checksum
        return ExportedPackage(
            content=content,
            manifest=manifest,
            validation=validation.model_dump(mode="json"),
            checksum=checksum,
        )

    def store(self, project_id: str, artifact_id: str, content: bytes) -> str:
        directory = (self.storage_root / project_id).resolve()
        if directory.parent != self.storage_root:
            raise ValueError("project artifact path escaped the configured storage root")
        directory.mkdir(parents=True, exist_ok=True)
        target = (directory / f"{artifact_id}.zip").resolve()
        if target.parent != directory:
            raise ValueError("artifact path escaped the project storage directory")
        temporary = target.with_suffix(".zip.tmp")
        temporary.write_bytes(content)
        temporary.replace(target)
        return f"{project_id}/{artifact_id}.zip"

    def read(self, storage_ref: str) -> bytes:
        target = self._resolve(storage_ref)
        if not target.is_file():
            raise ResourceNotFound("Artifact package was not found.")
        return target.read_bytes()

    def discard(self, storage_ref: str) -> None:
        self._resolve(storage_ref).unlink(missing_ok=True)

    async def _generate_and_validate(
        self,
        specification: PipelineSpecification,
        rows: tuple[dict[str, Any], ...],
    ) -> tuple[GeneratedPackage | GeneratedSqlPackage, PackageValidation]:
        language = specification.target.language
        if language is TargetLanguage.PYTHON:
            generator = PythonGenerator()
            package = generator.generate(specification)
            validation = (
                await generator.sample_validate(package, specification, rows, self.sandbox)
                if rows
                else generator.syntax_validate(package)
            )
            return package, validation
        elif language is TargetLanguage.JAVASCRIPT:
            javascript = JavaScriptGenerator()
            package = javascript.generate(specification)
            validation = (
                javascript.sample_validate(package, specification, rows)
                if rows
                else javascript.syntax_validate(package)
            )
            return package, validation
        sql = SqlGenerator()
        sql_package = sql.generate(specification)
        return sql_package, sql.syntax_validate(sql_package)

    @staticmethod
    def _masked_sample_output(
        specification: PipelineSpecification, rows: tuple[dict[str, Any], ...]
    ) -> str:
        if not rows:
            payload: dict[str, Any] = {
                "available": False,
                "reason": "No bounded sample was supplied for validation.",
                "rows": [],
            }
        else:
            result = execute(specification.model_dump(mode="json"), list(rows[:10]))
            sensitive = {
                field.target_name
                for field in specification.fields
                if field.pii_classification.value != "none"
            }
            masked = [
                {
                    name: "***" if name in sensitive and value is not None else value
                    for name, value in row.items()
                }
                for row in result["output_rows"][:10]
            ]
            payload = {"available": True, "masked": True, "rows": masked}
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n"

    @staticmethod
    def _readme(specification: PipelineSpecification, validation: PackageValidation) -> str:
        source = specification.sources[0]
        inputs = "\n".join(
            f"- `{field.source_name}` → `{field.target_name}` ({field.confirmed_type.value}, "
            f"{'required' if field.required else 'optional'})"
            for field in specification.fields
            if field.selected
        )
        transformations = (
            "\n".join(
                f"- {rule.order}. `{rule.kind.value}` on {', '.join(rule.inputs)}"
                for rule in specification.transformations
            )
            or "- None"
        )
        validations = (
            "\n".join(
                f"- `{rule.kind.value}` on `{rule.field}` ({rule.severity.value})"
                for rule in specification.validations
            )
            or "- None"
        )
        if specification.target.language is TargetLanguage.PYTHON:
            install = "python -m pip install -r requirements.txt\npython -m pytest"
            run = (
                "python pipeline.py --input-dir ./input --output-dir ./output "
                "--quarantine-dir ./quarantine --state-file ./state/processed.json"
            )
        elif specification.target.language is TargetLanguage.JAVASCRIPT:
            install = "node --version"
            run = (
                "node pipeline.mjs --input-dir ./input --output-dir ./output "
                "--quarantine-dir ./quarantine --state-file ./state/processed.json"
            )
        else:
            install = "Install a client for the selected SQL dialect."
            run = "Bind values from parameters.json, then execute pipeline.sql read-only."
        connection_note = (
            f"Set `{source.connection_ref}` in the runtime environment to the secret-managed "
            "connection configuration. Never place its value in this package."
            if source.kind == "database"
            else "No credential is required for a file source."
        )
        runtime = (
            f"Pattern `{source.runtime.filename_pattern}`, recursive={source.runtime.recursive}, "
            f"schema policy `{source.runtime.schema_policy.value}`, failure policy "
            f"`{source.runtime.failure_policy.value}`, processed tracking "
            f"`{source.runtime.processed_tracking.value}`."
            if source.kind == "file"
            else "The database query is read-only and bounded by the confirmed source contract."
        )
        return f"""# {specification.name}

Full scan-on-run pipeline generated from confirmed specification revision {specification.revision}.
It processes future inputs matching the same confirmed format; it is not a continuous watcher.

## Package layout

- Pipeline source/runtime files: executable implementation
- `pipeline-spec.json`: immutable confirmed behavior
- `.env.example`: variable names only, never secret values
- `sample-output.json`: bounded, masked validation example
- `artifact-manifest.json`: fingerprints, file hashes, and validation evidence
- `tests/`: generated contract checks where supported

## Input and output contract

{inputs}

Output format: `{specification.output.format.value}`; write mode: `{specification.output.write_mode.value}`;
UTF-8 encoding; atomic write: `{specification.output.atomic_write}`; null representation:
`{specification.output.null_representation}`.

## Transformations

{transformations}

## Validations

{validations}

## Prerequisites and install

```text
{install}
```

## Environment

{connection_note}

## Run once

```text
{run}
```

Folder runtime: {runtime} Inputs are never modified. A successful file checksum is recorded so a
repeat run skips unchanged files; changed or renamed files are processed again. Rejected rows and
failed files go to the quarantine directory according to the failure policy.

For scheduling, call the same scan-on-run command from Windows Task Scheduler or cron, for example
`0 * * * * cd /opt/pipeline && {run}`. Prevent overlapping invocations at the scheduler level.

## Assumptions, warnings, and limitations

- One confirmed source is supported in the MVP; multi-source joins remain deferred.
- Review generated logic and masked preview before production use.
- SQL packages are syntax-validated but require validation against a disposable target database.
- Validation status: `{validation.status.value}`; sample parity: `{validation.sample_matches_preview}`.

## Security and troubleshooting

Keep secrets in the deployment secret manager, restrict input/output directories, and run with the
least privileges. If schema validation fails, compare the incoming columns with `pipeline-spec.json`.
If dependencies fail, recreate a clean runtime and install the pinned requirements. Inspect the
quarantine error metadata; do not copy sensitive source rows into support tickets.

## Next integration

Version this package in your approved artifact repository, run its tests in CI, configure secrets at
deployment time, and invoke the scan-on-run command from your scheduler or orchestrator.
"""

    @staticmethod
    def _validate_paths(files: dict[str, str]) -> None:
        for name in files:
            path = PurePosixPath(name.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts or not name:
                raise ValueError(f"unsafe artifact path: {name}")

    @staticmethod
    def _scan(files: dict[str, str]) -> None:
        for name, content in files.items():
            for pattern in _SECRET_PATTERNS:
                if pattern.search(content):
                    raise SecretValueRejected(
                        "Generated package failed secret scanning.",
                        details={"file": name},
                    )

    @staticmethod
    def _archive(files: dict[str, str]) -> bytes:
        stream = BytesIO()
        with ZipFile(stream, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
            for name, content in sorted(files.items()):
                info = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                archive.writestr(info, content.encode("utf-8"))
        return stream.getvalue()

    def _resolve(self, storage_ref: str) -> Path:
        path = PurePosixPath(storage_ref)
        if path.is_absolute() or ".." in path.parts or len(path.parts) != 2:
            raise ResourceNotFound("Artifact package was not found.")
        target = (self.storage_root.joinpath(*path.parts)).resolve()
        if self.storage_root not in target.parents:
            raise ResourceNotFound("Artifact package was not found.")
        return target
