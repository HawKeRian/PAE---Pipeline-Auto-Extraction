"""Dialect SQL and sandboxed JavaScript generator parity tests."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from pae.domain.enums import (
    ArtifactStatus,
    DataType,
    OutputFormat,
    PiiClassification,
    SqlDialect,
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
from pae.generation.javascript_generator import JavaScriptGenerator
from pae.generation.sql_generator import SqlGenerator
from pae.persistence.errors import InvalidSpecificationRule, UnsupportedCapability

FIXTURES = Path(__file__).parent / "fixtures" / "transformation_cases.json"
GOLDEN_SQL = json.loads(
    (Path(__file__).parent / "golden" / "sql_dialects.json").read_text(encoding="utf-8")
)
GOLDEN_JAVASCRIPT = json.loads(
    (Path(__file__).parent / "golden" / "javascript_package.json").read_text(encoding="utf-8")
)


def fields() -> tuple[FieldDefinition, ...]:
    definitions = [
        ("id", DataType.INTEGER, PiiClassification.NONE),
        ("amount", DataType.DECIMAL, PiiClassification.NONE),
        ("category", DataType.STRING, PiiClassification.NONE),
        ("email", DataType.STRING, PiiClassification.CONFIRMED),
        ("note", DataType.STRING, PiiClassification.NONE),
        ("occurred_at", DataType.DATETIME, PiiClassification.NONE),
    ]
    return tuple(
        FieldDefinition(
            source_id="orders",
            source_name=name,
            target_name=name,
            inferred_type=data_type,
            confirmed_type=data_type,
            nullable=True,
            required=name in {"id", "amount"},
            confidence=1,
            null_percentage=0,
            pii_classification=pii,
        )
        for name, data_type, pii in definitions
    )


def base_specification(
    *,
    language: TargetLanguage,
    dialect: SqlDialect | None = None,
) -> PipelineSpecification:
    if language is TargetLanguage.SQL:
        assert dialect is not None
        database_type = {
            SqlDialect.POSTGRESQL: "postgresql",
            SqlDialect.MYSQL: "mysql",
            SqlDialect.SQL_SERVER: "sql_server",
        }[dialect]
        source = DatabaseSource(
            source_id="orders",
            database_type=database_type,  # type: ignore[arg-type]
            connection_ref="PAE_ORDERS_DATABASE",
            object_name="orders",
        )
        output = OutputContract(format=OutputFormat.SQL_RESULT)
    else:
        source = FileSource(
            source_id="orders",
            file_format="csv",
            original_name="orders.csv",
            runtime=FileDiscoveryContract(filename_pattern="*.csv"),
        )
        output = OutputContract(format=OutputFormat.JSON_LINES, path_template="{stem}.result")
    return PipelineSpecification(
        specification_id=UUID("12345678-1234-5678-1234-567812345678"),
        project_id=UUID("87654321-4321-8765-4321-876543218765"),
        revision=1,
        name="orders-pipeline",
        source_fingerprint="b" * 64,
        sources=(source,),
        fields=fields(),
        output=output,
        target=TargetRuntime(language=language, sql_dialect=dialect),
        confirmed_by="owner",
        confirmed_at=datetime(2026, 9, 27, tzinfo=UTC),
    )


def transformation(
    kind: TransformationKind,
    *,
    inputs: tuple[str, ...] = ("amount",),
    output: str | None = None,
    parameters: dict[str, object] | None = None,
) -> TransformationRule:
    return TransformationRule(
        rule_id=f"rule_{kind.value}",
        order=1,
        kind=kind,
        inputs=inputs,
        output=output,
        parameters=parameters or {},  # type: ignore[arg-type]
    )


SQL_RULES = (
    transformation(TransformationKind.INCLUDE, inputs=("id", "amount")),
    transformation(TransformationKind.EXCLUDE, inputs=("note",)),
    transformation(TransformationKind.RENAME, output="total"),
    transformation(TransformationKind.CAST, parameters={"type": "decimal"}),
    transformation(TransformationKind.FILTER, parameters={"operator": "gte", "value": 2}),
    transformation(
        TransformationKind.SORT,
        inputs=("amount",),
        parameters={"direction": "ascending", "nulls": "last"},
    ),
    transformation(
        TransformationKind.DEDUPLICATE,
        inputs=("id",),
        parameters={"keys": ["id"], "survivor": "first"},
    ),
    transformation(TransformationKind.REPLACE, parameters={"old": 1, "new": 2}),
    transformation(TransformationKind.HANDLE_NULL, parameters={"value": 0}),
    transformation(
        TransformationKind.DERIVE,
        inputs=("category", "note"),
        output="label",
        parameters={"operation": "concat", "separator": "-"},
    ),
    transformation(
        TransformationKind.AGGREGATE,
        output="total",
        parameters={"function": "sum", "group_by": ["category"]},
    ),
    transformation(
        TransformationKind.MASK,
        inputs=("email",),
        parameters={"strategy": "hash"},
    ),
)


@pytest.mark.parametrize("dialect", list(SqlDialect))
def test_sql_dialects_compile_every_mvp_transformation_and_match_golden(
    dialect: SqlDialect,
) -> None:
    generator = SqlGenerator()
    for rule in SQL_RULES:
        specification = base_specification(language=TargetLanguage.SQL, dialect=dialect).model_copy(
            update={"transformations": (rule,)}
        )
        package = generator.generate(specification)
        assert generator.syntax_validate(package).syntax_valid
        sql = package.files["pipeline.sql"]
        golden = GOLDEN_SQL[dialect.value]
        assert golden["identifier"] in sql
        if rule.kind is TransformationKind.MASK:
            assert golden["hash"] in sql
        if rule.kind is TransformationKind.SORT:
            assert golden["null_order"] in sql
        assert all(word not in sql.upper() for word in (" UPDATE ", " DELETE ", " INSERT "))


@pytest.mark.parametrize("dialect", list(SqlDialect))
def test_sql_executes_read_only_with_preview_parity_for_every_dialect(
    dialect: SqlDialect,
) -> None:
    rules = (
        transformation(TransformationKind.CAST, parameters={"type": "integer"}).model_copy(
            update={"order": 1}
        ),
        transformation(
            TransformationKind.FILTER, parameters={"operator": "gte", "value": 2}
        ).model_copy(update={"order": 2}),
        transformation(
            TransformationKind.SORT,
            inputs=("id",),
            parameters={"direction": "ascending", "nulls": "last"},
        ).model_copy(update={"order": 3}),
    )
    validation = ValidationRule(
        rule_id="amount_range",
        field="amount",
        kind=ValidationKind.RANGE,
        parameters={"minimum": 0},
    )
    specification = base_specification(language=TargetLanguage.SQL, dialect=dialect).model_copy(
        update={"transformations": rules, "validations": (validation,)}
    )
    package = SqlGenerator().generate(specification)
    rows = [
        {"id": 2, "amount": "2", "category": "b", "email": None, "note": None, "occurred_at": None},
        {"id": 1, "amount": "1", "category": "a", "email": None, "note": None, "occurred_at": None},
    ]
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE orders(id INTEGER, amount TEXT, category TEXT, email TEXT, "
        "note TEXT, occurred_at TEXT)"
    )
    connection.executemany(
        "INSERT INTO orders VALUES (:id, :amount, :category, :email, :note, :occurred_at)", rows
    )

    def executor(sql: str, parameters: dict[str, object]) -> list[dict[str, object]]:
        cursor = connection.execute(sql, parameters)
        columns = [item[0] for item in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

    validation_result = SqlGenerator.sample_validate(package, specification, tuple(rows), executor)
    assert validation_result.status is ArtifactStatus.SAMPLE_TESTED
    assert validation_result.sample_matches_preview
    connection.close()


def test_sql_parameterization_boundaries_and_unsupported_inputs() -> None:
    dangerous = "x' OR 1=1 --"
    specification = base_specification(
        language=TargetLanguage.SQL, dialect=SqlDialect.POSTGRESQL
    ).model_copy(
        update={
            "transformations": (
                transformation(
                    TransformationKind.FILTER,
                    inputs=("category",),
                    parameters={"operator": "eq", "value": dangerous},
                ),
            )
        }
    )
    package = SqlGenerator().generate(specification)
    assert dangerous not in package.files["pipeline.sql"]
    assert dangerous in package.parameters.values()
    file_specification = base_specification(language=TargetLanguage.JAVASCRIPT).model_copy(
        update={
            "target": TargetRuntime(language=TargetLanguage.SQL, sql_dialect=SqlDialect.POSTGRESQL),
            "output": OutputContract(format=OutputFormat.SQL_RESULT),
        }
    )
    with pytest.raises(UnsupportedCapability, match="database source"):
        SqlGenerator().generate(file_specification)

    unsafe_source = DatabaseSource(
        source_id="orders",
        database_type="postgresql",
        connection_ref="PAE_ORDERS_DATABASE",
        read_only_query="SELECT * FROM orders; DELETE FROM orders",
    )
    unsafe_specification = specification.model_copy(update={"sources": (unsafe_source,)})
    with pytest.raises(InvalidSpecificationRule, match="read-only"):
        SqlGenerator().generate(unsafe_specification)


@pytest.mark.parametrize("dialect", list(SqlDialect))
def test_sql_validation_queries_are_dialect_valid_or_rejected_early(
    dialect: SqlDialect,
) -> None:
    rules = [
        ValidationRule(rule_id="not_null", field="amount", kind=ValidationKind.NOT_NULL),
        ValidationRule(rule_id="unique", field="id", kind=ValidationKind.UNIQUE),
        ValidationRule(
            rule_id="range",
            field="amount",
            kind=ValidationKind.RANGE,
            parameters={"minimum": 0, "maximum": 100},
        ),
        ValidationRule(
            rule_id="allowed",
            field="category",
            kind=ValidationKind.ALLOWED_VALUES,
            parameters={"values": ["a", "b"]},
        ),
    ]
    if dialect is not SqlDialect.SQL_SERVER:
        rules.append(
            ValidationRule(
                rule_id="regex",
                field="category",
                kind=ValidationKind.REGEX,
                parameters={"pattern": "[a-z]+"},
            )
        )
    specification = base_specification(language=TargetLanguage.SQL, dialect=dialect).model_copy(
        update={"validations": tuple(rules)}
    )
    package = SqlGenerator().generate(specification)
    assert SqlGenerator.syntax_validate(package).syntax_valid
    assert package.files["validation_queries.sql"].count("SELECT") >= len(rules)

    if dialect is SqlDialect.SQL_SERVER:
        regex_specification = specification.model_copy(
            update={
                "validations": (
                    ValidationRule(
                        rule_id="regex",
                        field="category",
                        kind=ValidationKind.REGEX,
                        parameters={"pattern": "[a-z]+"},
                    ),
                )
            }
        )
        with pytest.raises(UnsupportedCapability, match="Regex"):
            SqlGenerator().generate(regex_specification)


def javascript_specification(*rules: TransformationRule) -> PipelineSpecification:
    return base_specification(language=TargetLanguage.JAVASCRIPT).model_copy(
        update={"transformations": rules}
    )


def test_javascript_matches_all_shared_transformation_fixtures() -> None:
    generator = JavaScriptGenerator()
    cases = json.loads(FIXTURES.read_text(encoding="utf-8"))
    for case in cases:
        rule = TransformationRule.model_validate(case["rule"])
        specification = javascript_specification(rule)
        package = generator.generate(specification)
        validation = generator.sample_validate(package, specification, tuple(case["rows"]))
        assert validation.sample_matches_preview, case["name"]
        assert validation.status is ArtifactStatus.SAMPLE_TESTED


def test_javascript_decimal_timezone_null_validation_and_database_adapter() -> None:
    rules = (
        transformation(TransformationKind.CAST, parameters={"type": "decimal"}),
        transformation(
            TransformationKind.CAST,
            inputs=("occurred_at",),
            parameters={"type": "datetime"},
        ).model_copy(update={"rule_id": "cast_time", "order": 2}),
        transformation(
            TransformationKind.HANDLE_NULL,
            inputs=("note",),
            parameters={"value": "unknown"},
        ).model_copy(update={"rule_id": "fill_note", "order": 3}),
    )
    validations = (
        ValidationRule(
            rule_id="amount_range",
            field="amount",
            kind=ValidationKind.RANGE,
            parameters={"minimum": 0},
        ),
        ValidationRule(
            rule_id="note_warning",
            field="note",
            kind=ValidationKind.ALLOWED_VALUES,
            severity=ValidationSeverity.WARNING,
            parameters={"values": ["known"]},
        ),
    )
    specification = javascript_specification(*rules).model_copy(update={"validations": validations})
    rows = (
        {
            "id": 1,
            "amount": "12.50",
            "category": "a",
            "email": "a@example.com",
            "note": None,
            "occurred_at": "2026-09-27T10:00:00+07:00",
        },
    )
    package = JavaScriptGenerator().generate(specification)
    assert JavaScriptGenerator.sample_validate(package, specification, rows).sample_matches_preview

    database_spec = specification.model_copy(
        update={
            "sources": (
                DatabaseSource(
                    source_id="orders",
                    database_type="postgresql",
                    connection_ref="PAE_ORDERS_DATABASE",
                    object_name="orders",
                ),
            )
        }
    )
    database_package = JavaScriptGenerator().generate(database_spec)
    assert json.loads(database_package.files["package.json"])["dependencies"]["pg"]
    assert "readDatabase" in database_package.files["pipeline.mjs"]


@pytest.mark.parametrize(
    ("kind", "parameters", "rows"),
    [
        (ValidationKind.NOT_NULL, {}, ({"amount": None},)),
        (ValidationKind.UNIQUE, {}, ({"amount": "1"}, {"amount": "1"})),
        (ValidationKind.RANGE, {"minimum": 1, "maximum": 2}, ({"amount": 3},)),
        (ValidationKind.REGEX, {"pattern": r"[A-Z]+"}, ({"amount": "lower"},)),
        (ValidationKind.ALLOWED_VALUES, {"values": ["yes"]}, ({"amount": "no"},)),
    ],
)
def test_javascript_matches_all_validation_fixtures(
    kind: ValidationKind,
    parameters: dict[str, object],
    rows: tuple[dict[str, object], ...],
) -> None:
    rule = ValidationRule(
        rule_id="validation_rule",
        field="amount",
        kind=kind,
        parameters=parameters,  # type: ignore[arg-type]
    )
    specification = javascript_specification().model_copy(update={"validations": (rule,)})
    package = JavaScriptGenerator().generate(specification)
    result = JavaScriptGenerator.sample_validate(package, specification, rows)  # type: ignore[arg-type]
    assert result.status is ArtifactStatus.SAMPLE_TESTED


def test_javascript_golden_generated_test_and_unsupported_join(tmp_path: Path) -> None:
    specification = javascript_specification()
    package = JavaScriptGenerator().generate(specification)
    assert sorted(package.files) == GOLDEN_JAVASCRIPT["files"]
    expected_hash = "".join(f"{part:016x}" for part in GOLDEN_JAVASCRIPT["runtime_sha256_uint64"])
    assert hashlib.sha256(package.files["runtime.mjs"].encode()).hexdigest() == expected_hash
    root = tmp_path / "package"
    for name, content in package.files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    completed = subprocess.run(
        ["node", "--test", str(root / "tests" / "runtime.test.mjs")],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0

    join = transformation(TransformationKind.JOIN, inputs=("id",))
    with pytest.raises(UnsupportedCapability, match="Deferred"):
        JavaScriptGenerator().generate(javascript_specification(join))


def test_generated_javascript_cli_is_idempotent_and_atomic(tmp_path: Path) -> None:
    specification = javascript_specification(
        transformation(TransformationKind.CAST, parameters={"type": "decimal"})
    )
    package = JavaScriptGenerator().generate(specification)
    root = tmp_path / "package"
    for name, content in package.files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "orders.csv").write_text(
        'id,amount,category,email,note,occurred_at\n1,1.20,"a,b",a@example.com,,\n',
        encoding="utf-8",
    )
    command = [
        "node",
        str(root / "pipeline.mjs"),
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
    assert json.loads(first.stdout)["processed"] == 1
    assert json.loads(second.stdout)["skipped"] == 1
    output_file = tmp_path / "output" / "orders.result.jsonl"
    assert output_file.exists()
    assert json.loads(output_file.read_text(encoding="utf-8"))["category"] == "a,b"
    assert not list((tmp_path / "output").glob("*.tmp"))

    append_specification = specification.model_copy(
        update={"output": specification.output.model_copy(update={"write_mode": WriteMode.APPEND})}
    )
    append_package = JavaScriptGenerator().generate(append_specification)
    for name, content in append_package.files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    append_command = command.copy()
    append_command[5] = str(tmp_path / "append-output")
    append_command[9] = str(tmp_path / "append-state.json")
    assert (
        subprocess.run(append_command, capture_output=True, text=True, check=False).returncode == 0
    )
    (input_dir / "orders.csv").write_text(
        "id,amount,category,email,note,occurred_at\n1,2.30,a,a@example.com,,\n",
        encoding="utf-8",
    )
    assert (
        subprocess.run(append_command, capture_output=True, text=True, check=False).returncode == 0
    )
    lines = (
        (tmp_path / "append-output" / "orders.result.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert len(lines) == 2
    assert not list((tmp_path / "append-output").glob("*.tmp"))
