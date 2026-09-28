"""Specification builder validation and capability tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from pae.ai.models import TransformationDraft, ValidationDraft
from pae.domain.enums import (
    DataType,
    OutputFormat,
    TargetLanguage,
    TransformationKind,
    ValidationKind,
)
from pae.domain.models import OutputContract, TargetRuntime
from pae.persistence.errors import InvalidSpecificationRule, UnsupportedCapability
from pae.profiling.models import ConfirmedField, ConfirmedSchema
from pae.specification import SpecificationConfirmationRequest, build_specification


def schema() -> ConfirmedSchema:
    return ConfirmedSchema(
        project_id="12345678-1234-5678-1234-567812345678",
        revision=1,
        fields=(
            ConfirmedField(
                name="amount",
                inferred_type=DataType.STRING,
                confirmed_type=DataType.DECIMAL,
                nullable=False,
                required=True,
                confidence=1,
                null_percentage=0,
            ),
        ),
        schema_fingerprint="a" * 64,
        confirmed_by="owner",
        confirmed_at=datetime.now(UTC),
    )


def source() -> dict[str, object]:
    return {
        "kind": "file",
        "revision": 1,
        "config": {
            "file_format": "csv",
            "original_name": "orders.csv",
            "encoding": "utf-8",
            "delimiter": ",",
            "runtime": {
                "filename_pattern": "*.csv",
                "recursive": False,
                "schema_policy": "strict",
            },
            "profile": {"sampled_rows": 10},
        },
    }


def request(*rules: TransformationDraft) -> SpecificationConfirmationRequest:
    return SpecificationConfirmationRequest(
        proposal_id="proposal-1",
        name="orders-pipeline",
        transformations=rules,
        validations=(
            ValidationDraft(
                rule_id="amount_range",
                field="amount",
                kind=ValidationKind.RANGE,
                parameters={"minimum": 0},
            ),
        ),
        output=OutputContract(format=OutputFormat.CSV),
        target=TargetRuntime(language=TargetLanguage.PYTHON),
        assumptions_acknowledged=True,
    )


def test_builds_specification_from_user_edited_rules_and_confirmed_schema() -> None:
    rule = TransformationDraft(
        rule_id="cast_amount",
        order=1,
        kind=TransformationKind.CAST,
        inputs=("amount",),
        output=None,
        parameters={"type": "decimal"},
    )
    specification = build_specification(
        schema().project_id, source(), schema(), request(rule), "owner"
    )
    assert specification.fields[0].confirmed_type is DataType.DECIMAL
    assert specification.transformations[0].rule_id == "cast_amount"
    assert specification.validations[0].field == "amount"
    assert specification.sources[0].runtime.filename_pattern == "*.csv"  # type: ignore[union-attr]


def test_unknown_fields_join_and_incompatible_output_are_rejected() -> None:
    unknown = TransformationDraft(
        rule_id="bad",
        order=1,
        kind=TransformationKind.FILTER,
        inputs=("missing",),
        output=None,
        parameters={"operator": ">", "value": 0},
    )
    with pytest.raises(InvalidSpecificationRule, match="outside"):
        build_specification(schema().project_id, source(), schema(), request(unknown), "owner")

    join = unknown.model_copy(
        update={"rule_id": "join_sources", "kind": TransformationKind.JOIN, "inputs": ("amount",)}
    )
    with pytest.raises(UnsupportedCapability, match="deferred"):
        build_specification(schema().project_id, source(), schema(), request(join), "owner")

    incompatible = request().model_copy(
        update={
            "output": OutputContract(format=OutputFormat.PARQUET),
            "target": TargetRuntime(language=TargetLanguage.JAVASCRIPT),
        }
    )
    with pytest.raises(UnsupportedCapability, match="not supported"):
        build_specification(schema().project_id, source(), schema(), incompatible, "owner")


def test_rule_order_and_ids_are_validated_for_full_list_editing() -> None:
    first = TransformationDraft(
        rule_id="one",
        order=1,
        kind=TransformationKind.INCLUDE,
        inputs=("amount",),
        output=None,
        parameters={},
    )
    gap = first.model_copy(update={"rule_id": "two", "order": 3})
    with pytest.raises(ValidationError, match="consecutive"):
        request(first, gap)


@pytest.mark.parametrize(
    "kind",
    [
        TransformationKind.INCLUDE,
        TransformationKind.EXCLUDE,
        TransformationKind.RENAME,
        TransformationKind.CAST,
        TransformationKind.FILTER,
        TransformationKind.SORT,
        TransformationKind.DEDUPLICATE,
        TransformationKind.REPLACE,
        TransformationKind.HANDLE_NULL,
        TransformationKind.DERIVE,
        TransformationKind.AGGREGATE,
        TransformationKind.MASK,
    ],
)
def test_all_mvp_transformation_kinds_pass_capability_validation(
    kind: TransformationKind,
) -> None:
    rule = TransformationDraft(
        rule_id=f"rule_{kind.value}",
        order=1,
        kind=kind,
        inputs=("amount",),
        output="calculated"
        if kind in {TransformationKind.RENAME, TransformationKind.DERIVE}
        else None,
        parameters={},
    )
    built = build_specification(schema().project_id, source(), schema(), request(rule), "owner")
    assert built.transformations[0].kind is kind
