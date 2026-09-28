"""Shared semantics, sandbox, preview, and generated Python package tests."""

from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from pae.domain.enums import (
    DataType,
    FileFailurePolicy,
    OutputFormat,
    PiiClassification,
    SchemaCompatibilityPolicy,
    TargetLanguage,
    TransformationKind,
    ValidationKind,
    ValidationSeverity,
    WriteMode,
)
from pae.domain.models import (
    DatabaseSource,
    FieldDefinition,
    FileDiscoveryContract,
    FileSource,
    OutputContract,
    PipelineSpecification,
    TargetRuntime,
    TransformationRule,
    ValidationRule,
)
from pae.generation.python_generator import PythonGenerator
from pae.persistence.errors import (
    SandboxExecutionFailed,
    SandboxResourceLimit,
    SandboxTimeout,
    SchemaChanged,
    UnsupportedCapability,
)
from pae.preview.service import PreviewService
from pae.runtime_core import execute
from pae.sandbox import SandboxRunner

FIXTURES = Path(__file__).parent / "fixtures" / "transformation_cases.json"


def specification(*, joins: bool = False) -> PipelineSpecification:
    fields = (
        FieldDefinition(
            source_id="orders",
            source_name="id",
            target_name="id",
            inferred_type=DataType.INTEGER,
            confirmed_type=DataType.INTEGER,
            nullable=False,
            required=True,
            confidence=1,
            null_percentage=0,
            distinct_count=2,
        ),
        FieldDefinition(
            source_id="orders",
            source_name="amount",
            target_name="amount",
            inferred_type=DataType.STRING,
            confirmed_type=DataType.DECIMAL,
            nullable=True,
            required=True,
            confidence=1,
            null_percentage=0,
        ),
        FieldDefinition(
            source_id="orders",
            source_name="email",
            target_name="email",
            inferred_type=DataType.STRING,
            confirmed_type=DataType.STRING,
            nullable=True,
            required=False,
            confidence=1,
            null_percentage=0,
            pii_classification=PiiClassification.CONFIRMED,
        ),
    )
    transformations = (
        TransformationRule(
            rule_id="cast_amount",
            order=1,
            kind=TransformationKind.CAST,
            inputs=("amount",),
            parameters={"type": "decimal"},
        ),
        TransformationRule(
            rule_id="mask_email",
            order=2,
            kind=TransformationKind.MASK,
            inputs=("email",),
            parameters={"strategy": "email"},
        ),
    )
    if joins:
        transformations = transformations + (
            TransformationRule(
                rule_id="join_other",
                order=3,
                kind=TransformationKind.JOIN,
                inputs=("id",),
            ),
        )
    return PipelineSpecification(
        specification_id=UUID("12345678-1234-5678-1234-567812345678"),
        project_id=UUID("87654321-4321-8765-4321-876543218765"),
        revision=1,
        name="orders-pipeline",
        source_fingerprint="a" * 64,
        sources=(
            FileSource(
                source_id="orders",
                file_format="csv",
                original_name="sample.csv",
                delimiter=",",
                runtime=FileDiscoveryContract(
                    filename_pattern="*.csv", failure_policy=FileFailurePolicy.QUARANTINE
                ),
            ),
        ),
        fields=fields,
        transformations=transformations,
        validations=(
            ValidationRule(
                rule_id="positive",
                field="amount",
                kind=ValidationKind.RANGE,
                severity=ValidationSeverity.ERROR,
                parameters={"minimum": 0},
            ),
            ValidationRule(
                rule_id="email_warning",
                field="email",
                kind=ValidationKind.REGEX,
                severity=ValidationSeverity.WARNING,
                parameters={"pattern": r".+@.+"},
            ),
        ),
        output=OutputContract(format=OutputFormat.CSV, path_template="{stem}.result"),
        target=TargetRuntime(language=TargetLanguage.PYTHON),
        confirmed_by="owner",
        confirmed_at=datetime(2026, 9, 27, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    "case", json.loads(FIXTURES.read_text(encoding="utf-8")), ids=lambda case: case["name"]
)
def test_shared_expected_output_for_every_mvp_transformation(case: dict[str, object]) -> None:
    result = execute({"transformations": [case["rule"]], "validations": []}, case["rows"])  # type: ignore[arg-type]
    assert result["output_rows"] == case["expected"]


def test_validation_errors_warnings_and_rejections_are_distinct() -> None:
    result = execute(
        specification().model_dump(mode="json"),
        [
            {"id": 1, "amount": "-1", "email": "invalid"},
            {"id": 2, "amount": "2", "email": "ok@example.com"},
        ],
    )
    assert len(result["issues"]) == 2
    assert result["rejected_rows"][0]["rule_id"] == "positive"
    assert result["input_count"] == 2
    assert result["output_count"] == 1


@pytest.mark.parametrize(
    ("kind", "parameters", "rows", "expected"),
    [
        ("not_null", {}, [{"value": None}], 1),
        ("unique", {}, [{"value": "a"}, {"value": "a"}], 1),
        ("range", {"minimum": 1, "maximum": 2}, [{"value": 3}], 1),
        ("regex", {"pattern": r"[A-Z]+"}, [{"value": "lower"}], 1),
        ("allowed_values", {"values": ["yes"]}, [{"value": "no"}], 1),
    ],
)
def test_shared_validation_semantics(
    kind: str,
    parameters: dict[str, object],
    rows: list[dict[str, object]],
    expected: int,
) -> None:
    result = execute(
        {
            "transformations": [],
            "validations": [
                {
                    "rule_id": "validation_rule",
                    "field": "value",
                    "kind": kind,
                    "severity": "error",
                    "parameters": parameters,
                }
            ],
        },
        rows,
    )
    assert len(result["issues"]) == expected


def test_preview_masks_sensitive_rows_and_reports_schema_change(tmp_path: Path) -> None:
    async def scenario() -> None:
        service = PreviewService(SandboxRunner(tmp_path / "workspaces"))
        preview = await service.preview(
            specification(),
            (
                {"id": 1, "amount": "-1", "email": "alice@example.com"},
                {"id": 2, "amount": "2", "email": "bob@example.com"},
            ),
        )
        assert preview.status == "sample_tested"
        assert preview.before_rows[0]["email"] == "***"
        assert preview.rejected_rows[0].row["email"] == "***"
        assert preview.errors and not preview.warnings
        assert not list((tmp_path / "workspaces").iterdir())
        with pytest.raises(SchemaChanged, match="missing"):
            await service.preview(specification(), ({"id": 1},))

    asyncio.run(scenario())


def test_sandbox_isolation_limits_cancellation_and_cleanup(tmp_path: Path) -> None:
    async def scenario() -> None:
        root = tmp_path / "sandbox"
        runner = SandboxRunner(root, timeout_seconds=1)
        assert (await runner.run({"operation": "network_probe"}))["network_blocked"] is True
        assert (await runner.run({"operation": "process_probe"}))["process_blocked"] is True
        assert (await runner.run({"operation": "filesystem_probe", "path": str(tmp_path)}))[
            "filesystem_blocked"
        ] is True
        with pytest.raises(SandboxTimeout):
            await runner.run({"operation": "sleep_probe", "seconds": 1}, timeout_seconds=0.1)
        with pytest.raises(SandboxExecutionFailed):
            await runner.run({"operation": "crash_probe"})
        with pytest.raises(SandboxResourceLimit):
            await SandboxRunner(root, output_limit_bytes=20).run(
                {
                    "operation": "preview",
                    "specification": {"transformations": []},
                    "rows": [{"long": "x" * 100}],
                }
            )
        with pytest.raises(SandboxResourceLimit):
            await SandboxRunner(root, memory_limit_bytes=1).run({"operation": "network_probe"})
        task = asyncio.create_task(runner.run({"operation": "sleep_probe", "seconds": 1}))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not list(root.iterdir())

    asyncio.run(scenario())


def test_generator_is_deterministic_syntax_checked_and_matches_preview(tmp_path: Path) -> None:
    async def scenario() -> None:
        generator = PythonGenerator()
        first = generator.generate(specification())
        second = generator.generate(specification())
        assert first.checksum == second.checksum
        assert first.files == second.files
        assert generator.syntax_validate(first).status.value == "syntax_validated"
        validation = await generator.sample_validate(
            first,
            specification(),
            ({"id": 1, "amount": "2", "email": "a@example.com"},),
            SandboxRunner(tmp_path / "sandbox"),
        )
        assert validation.status.value == "sample_tested"
        assert validation.sample_matches_preview
        combined = "\n".join(first.files.values())
        assert "password=" not in combined.lower()
        assert str(tmp_path) not in combined
        with pytest.raises(UnsupportedCapability, match="Deferred"):
            generator.generate(specification(joins=True))

    asyncio.run(scenario())


def test_generator_golden_template_and_database_adapter() -> None:
    golden = json.loads(
        (Path(__file__).parent / "golden" / "python_template.json").read_text(encoding="utf-8")
    )
    package = PythonGenerator().generate(specification())
    assert sorted(package.files) == golden["files"]
    expected_hash = "".join(f"{part:016x}" for part in golden["sha256_uint64"])
    assert hashlib.sha256(package.files["pipeline.py"].encode()).hexdigest() == expected_hash

    database_spec = specification().model_copy(
        update={
            "sources": (
                DatabaseSource(
                    source_id="orders",
                    database_type="postgresql",
                    connection_ref="PAE_ORDERS_DATABASE",
                    schema_name="public",
                    object_name="orders",
                ),
            )
        }
    )
    database_package = PythonGenerator().generate(database_spec)
    assert "psycopg[binary]" in database_package.files["requirements.txt"]
    assert "PAE_ORDERS_DATABASE" in database_package.files["pipeline_spec.json"]
    assert "read_database" in database_package.files["pipeline.py"]


def test_generated_cli_processes_folder_once_and_writes_manifest(tmp_path: Path) -> None:
    package = PythonGenerator().generate(specification())
    package_dir = tmp_path / "package"
    for name, content in package.files.items():
        target = package_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "b.csv").write_text("id,amount,email\n2,2,b@example.com\n", encoding="utf-8")
    (input_dir / "a.csv").write_text("id,amount,email\n1,1,a@example.com\n", encoding="utf-8")
    command = [
        sys.executable,
        str(package_dir / "pipeline.py"),
        "--input-dir",
        str(input_dir),
        "--output-dir",
        str(tmp_path / "output"),
        "--quarantine-dir",
        str(tmp_path / "quarantine"),
        "--state-file",
        str(tmp_path / "state.json"),
    ]
    first = subprocess.run(command, capture_output=True, text=True, check=False)
    second = subprocess.run(command, capture_output=True, text=True, check=False)
    assert first.returncode == 0
    assert json.loads(first.stdout)["processed"] == 2
    assert json.loads(second.stdout)["skipped"] == 2
    assert (tmp_path / "output" / "a.result.csv").exists()
    assert len(json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))["processed"]) == 2
    (input_dir / "a.csv").write_text("id,amount,email\n1,3,a@example.com\n", encoding="utf-8")
    third = subprocess.run(command, capture_output=True, text=True, check=False)
    assert json.loads(third.stdout)["processed"] == 1
    output_lines = (tmp_path / "output" / "a.result.csv").read_text(encoding="utf-8").splitlines()
    assert len(output_lines) == 2
    assert "3" in output_lines[1]
    (input_dir / "a.csv").rename(input_dir / "renamed.csv")
    renamed = subprocess.run(command, capture_output=True, text=True, check=False)
    assert renamed.returncode == 0
    assert json.loads(renamed.stdout)["processed"] == 1
    assert (tmp_path / "output" / "renamed.result.csv").exists()
    (input_dir / "renamed.csv").rename(input_dir / "a.csv")

    append_spec = specification().model_copy(
        update={
            "output": specification().output.model_copy(update={"write_mode": WriteMode.APPEND})
        }
    )
    append_package = PythonGenerator().generate(append_spec)
    for name, content in append_package.files.items():
        target = package_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    append_command = command.copy()
    append_command[5] = str(tmp_path / "append-output")
    append_command[9] = str(tmp_path / "append-state.json")
    initial_append = subprocess.run(append_command, capture_output=True, text=True, check=False)
    assert initial_append.returncode == 0
    (input_dir / "a.csv").write_text("id,amount,email\n1,4,a@example.com\n", encoding="utf-8")
    repeated_append = subprocess.run(append_command, capture_output=True, text=True, check=False)
    assert repeated_append.returncode == 0
    append_lines = (
        (tmp_path / "append-output" / "a.result.csv").read_text(encoding="utf-8").splitlines()
    )
    assert len(append_lines) == 3
    assert not list((tmp_path / "append-output").glob("*.tmp"))


def test_generated_cli_quarantines_schema_incompatible_file(tmp_path: Path) -> None:
    package = PythonGenerator().generate(specification())
    package_dir = tmp_path / "package"
    for name, content in package.files.items():
        target = package_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "bad.csv").write_text("id,email\n1,a@example.com\n", encoding="utf-8")
    (input_dir / "good.csv").write_text("id,amount,email\n2,2,b@example.com\n", encoding="utf-8")
    quarantine = tmp_path / "quarantine"
    completed = subprocess.run(
        [
            sys.executable,
            str(package_dir / "pipeline.py"),
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(tmp_path / "output"),
            "--quarantine-dir",
            str(quarantine),
            "--state-file",
            str(tmp_path / "state.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert json.loads(completed.stdout)["processed"] == 1
    assert json.loads(completed.stdout)["failed"] == 1
    assert (tmp_path / "output" / "good.result.csv").exists()
    assert (quarantine / "bad.csv").exists()
    assert (quarantine / "bad.csv.error.json").exists()


def test_generated_cli_allows_optional_and_extra_columns_by_policy(tmp_path: Path) -> None:
    base = specification()
    source = base.sources[0]
    assert isinstance(source, FileSource)
    runtime = source.runtime.model_copy(
        update={"schema_policy": SchemaCompatibilityPolicy.ALLOW_EXTRA_COLUMNS}
    )
    package = PythonGenerator().generate(
        base.model_copy(update={"sources": (source.model_copy(update={"runtime": runtime}),)})
    )
    package_dir = tmp_path / "package"
    for name, content in package.files.items():
        target = package_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    # email is optional and an unknown source column is explicitly permitted.
    (input_dir / "extra.csv").write_text("id,amount,note\n1,2,ok\n", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(package_dir / "pipeline.py"),
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(tmp_path / "output"),
            "--quarantine-dir",
            str(tmp_path / "quarantine"),
            "--state-file",
            str(tmp_path / "state.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["processed"] == 1
    assert (tmp_path / "output" / "extra.result.csv").exists()
