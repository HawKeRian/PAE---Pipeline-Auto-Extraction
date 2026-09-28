"""Contract tests for the versioned Pipeline Specification."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from pae.domain.capabilities import MVP_CAPABILITIES
from pae.domain.enums import (
    DataType,
    OutputFormat,
    PiiClassification,
    SqlDialect,
    TargetLanguage,
    TransformationKind,
    ValidationKind,
)
from pae.domain.fingerprints import model_fingerprint
from pae.domain.models import (
    DatabaseSource,
    FieldDefinition,
    FileDiscoveryContract,
    FileSource,
    JoinDefinition,
    OutputContract,
    PipelineSpecification,
    TargetRuntime,
    TransformationRule,
    ValidationRule,
)

PROJECT_ID = UUID("11111111-1111-4111-8111-111111111111")
SPECIFICATION_ID = UUID("22222222-2222-4222-8222-222222222222")
SOURCE_FINGERPRINT = "a" * 64


def valid_specification() -> PipelineSpecification:
    return PipelineSpecification(
        specification_id=SPECIFICATION_ID,
        project_id=PROJECT_ID,
        revision=1,
        name="customer-active-transactions",
        source_fingerprint=SOURCE_FINGERPRINT,
        sources=(
            FileSource(
                source_id="transactions",
                file_format="csv",
                original_name="transactions.csv",
                runtime=FileDiscoveryContract(filename_pattern="*.csv"),
            ),
        ),
        fields=(
            FieldDefinition(
                source_id="transactions",
                source_name="cust_id",
                target_name="customer_id",
                inferred_type=DataType.STRING,
                confirmed_type=DataType.STRING,
                nullable=False,
                confidence=0.99,
                null_percentage=0,
                distinct_count=2,
                pii_classification=PiiClassification.NONE,
                samples_masked=("C-1001",),
            ),
            FieldDefinition(
                source_id="transactions",
                source_name="amount",
                target_name="total_amount",
                inferred_type=DataType.STRING,
                confirmed_type=DataType.DECIMAL,
                nullable=False,
                confidence=0.91,
                null_percentage=0,
            ),
        ),
        transformations=(
            TransformationRule(
                rule_id="cast_amount",
                order=1,
                kind=TransformationKind.CAST,
                inputs=("amount",),
                output="total_amount",
                parameters={"decimal_separator": "."},
            ),
        ),
        output=OutputContract(format=OutputFormat.CSV),
        target=TargetRuntime(language=TargetLanguage.PYTHON),
        confirmed_by="project-owner",
        confirmed_at=datetime(2026, 9, 26, tzinfo=UTC),
    )


def test_valid_specification_exports_versioned_json_schema() -> None:
    specification = valid_specification()
    schema = PipelineSpecification.model_json_schema()

    assert specification.specification_version == "1.0"
    assert schema["title"] == "PipelineSpecification"
    assert schema["additionalProperties"] is False
    assert specification.sources[0].runtime.filename_pattern == "*.csv"
    assert specification.sources[0].runtime.failure_policy == "quarantine"


@pytest.mark.parametrize("pattern", ["../*.csv", "/incoming/*.csv", "C:/data/*.csv"])
def test_file_discovery_rejects_unsafe_patterns(pattern: str) -> None:
    with pytest.raises(ValidationError, match="relative glob"):
        FileDiscoveryContract(filename_pattern=pattern)


def test_recursive_glob_requires_recursive_mode() -> None:
    with pytest.raises(ValidationError, match="recursive must be true"):
        FileDiscoveryContract(filename_pattern="**/*.csv", recursive=False)

    contract = FileDiscoveryContract(filename_pattern="**/*.csv", recursive=True)
    assert contract.discovery_order == "path_ascending"


def test_file_source_requires_confirmed_runtime_contract() -> None:
    with pytest.raises(ValidationError, match="runtime"):
        FileSource.model_validate(
            {
                "source_id": "transactions",
                "file_format": "csv",
                "original_name": "sample.csv",
            }
        )


def test_unknown_transformation_field_is_rejected() -> None:
    data = valid_specification().model_dump()
    data["transformations"] = (
        TransformationRule(
            rule_id="bad_rule",
            order=1,
            kind=TransformationKind.CAST,
            inputs=("missing_field",),
        ),
    )

    with pytest.raises(ValidationError, match="unknown selected fields"):
        PipelineSpecification.model_validate(data)


def test_duplicate_transformation_order_is_rejected() -> None:
    data = valid_specification().model_dump()
    data["transformations"] = (
        TransformationRule(
            rule_id="first_rule",
            order=1,
            kind=TransformationKind.CAST,
            inputs=("amount",),
        ),
        TransformationRule(
            rule_id="second_rule",
            order=1,
            kind=TransformationKind.RENAME,
            inputs=("cust_id",),
        ),
    )

    with pytest.raises(ValidationError, match="order values must be unique"):
        PipelineSpecification.model_validate(data)


def test_database_source_rejects_embedded_password() -> None:
    with pytest.raises(ValidationError, match="password"):
        DatabaseSource.model_validate(
            {
                "source_id": "warehouse",
                "kind": "database",
                "database_type": "postgresql",
                "connection_ref": "secret://warehouse/read-only",
                "object_name": "transactions",
                "password": "must-not-be-accepted",
            }
        )


@pytest.mark.parametrize(
    "object_name, query",
    [(None, None), ("transactions", "SELECT * FROM transactions")],
)
def test_database_source_requires_exactly_one_read_target(
    object_name: str | None, query: str | None
) -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        DatabaseSource(
            source_id="warehouse",
            database_type="postgresql",
            connection_ref="secret://warehouse/read-only",
            object_name=object_name,
            read_only_query=query,
        )


def test_target_runtime_requires_dialect_only_for_sql() -> None:
    with pytest.raises(ValidationError, match="required for SQL"):
        TargetRuntime(language=TargetLanguage.SQL)

    with pytest.raises(ValidationError, match="valid only for SQL"):
        TargetRuntime(language=TargetLanguage.PYTHON, sql_dialect=SqlDialect.POSTGRESQL)


def test_join_contract_rejects_mismatched_keys_and_self_join() -> None:
    with pytest.raises(ValidationError, match="same length"):
        JoinDefinition(
            join_id="customer_orders",
            left_source_id="customers",
            right_source_id="orders",
            join_type="inner",
            left_keys=("customer_id",),
            right_keys=("customer_id", "region"),
            expected_cardinality="one_to_many",
        )

    with pytest.raises(ValidationError, match="different sources"):
        JoinDefinition(
            join_id="self_join",
            left_source_id="customers",
            right_source_id="customers",
            join_type="inner",
            left_keys=("customer_id",),
            right_keys=("parent_id",),
            expected_cardinality="one_to_many",
        )


def test_specification_rejects_duplicate_sources_and_unknown_field_source() -> None:
    source = valid_specification().sources[0]
    data = valid_specification().model_dump()
    data["sources"] = (source, source)
    with pytest.raises(ValidationError, match="source_id values must be unique"):
        PipelineSpecification.model_validate(data)

    data = valid_specification().model_dump()
    fields = list(valid_specification().fields)
    fields[0] = fields[0].model_copy(update={"source_id": "missing"})
    data["fields"] = fields
    with pytest.raises(ValidationError, match="unknown sources"):
        PipelineSpecification.model_validate(data)


def test_specification_rejects_duplicate_targets_and_unknown_validation_field() -> None:
    data = valid_specification().model_dump()
    fields = list(valid_specification().fields)
    fields[1] = fields[1].model_copy(update={"target_name": "customer_id"})
    data["fields"] = fields
    with pytest.raises(ValidationError, match="target_name values must be unique"):
        PipelineSpecification.model_validate(data)

    data = valid_specification().model_dump()
    data["validations"] = (
        ValidationRule(
            rule_id="missing_not_null",
            field="missing_field",
            kind=ValidationKind.NOT_NULL,
        ),
    )
    with pytest.raises(ValidationError, match="validations reference unknown"):
        PipelineSpecification.model_validate(data)


def test_specification_rejects_unknown_join_source_and_naive_confirmation_time() -> None:
    data = valid_specification().model_dump()
    data["joins"] = (
        JoinDefinition(
            join_id="unknown_source_join",
            left_source_id="transactions",
            right_source_id="missing",
            join_type="left",
            left_keys=("cust_id",),
            right_keys=("cust_id",),
            expected_cardinality="one_to_many",
        ),
    )
    with pytest.raises(ValidationError, match="unknown source"):
        PipelineSpecification.model_validate(data)

    data = valid_specification().model_dump()
    data["confirmed_at"] = datetime(2026, 9, 26)
    with pytest.raises(ValidationError, match="include a timezone"):
        PipelineSpecification.model_validate(data)


def test_fingerprint_is_stable_for_equivalent_models() -> None:
    first = valid_specification()
    second = PipelineSpecification.model_validate(first.model_dump())

    assert model_fingerprint(first) == model_fingerprint(second)
    assert len(model_fingerprint(first)) == 64


def test_mvp_capabilities_fail_closed_for_join() -> None:
    assert all(
        TransformationKind.JOIN not in capability.transformations for capability in MVP_CAPABILITIES
    )
