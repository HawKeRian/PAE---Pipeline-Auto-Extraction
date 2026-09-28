"""Schema inference, quality metric, masking, and confirmation-model tests."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from pae.domain.enums import DataType, PiiClassification
from pae.profiling.models import ConfirmedField, SchemaConfirmation
from pae.profiling.service import SchemaProfiler


def test_profile_infers_types_quality_metrics_formats_and_mixed_values() -> None:
    rows = (
        {
            "customer_id": "C-1",
            "amount": "10.50",
            "active": "true",
            "created": "27/09/2026",
            "mixed": "10",
            "note": "ภาษาไทย",
        },
        {
            "customer_id": "C-2",
            "amount": "20.25",
            "active": "false",
            "created": "28/09/2026",
            "mixed": "ข้อความ",
            "note": None,
        },
        {
            "customer_id": "C-2",
            "amount": "",
            "active": "true",
            "created": "29/09/2026",
            "mixed": "30",
        },
    )
    result = SchemaProfiler().profile(rows)
    fields = {field.name: field for field in result.fields}
    assert fields["amount"].inferred_type is DataType.DECIMAL
    assert fields["amount"].null_count == 1
    assert fields["amount"].null_percentage == pytest.approx(100 / 3)
    assert fields["amount"].minimum == 10.5
    assert fields["amount"].maximum == 20.25
    assert fields["active"].inferred_type is DataType.BOOLEAN
    assert fields["created"].inferred_type is DataType.DATE
    assert fields["created"].detected_format == "dd/mm/yyyy"
    assert fields["created"].minimum == "2026-09-27"
    assert fields["mixed"].mixed_types is True
    assert fields["mixed"].confidence == pytest.approx(2 / 3)
    assert fields["note"].null_count == 2
    assert fields["note"].distinct_count == 1
    assert fields["note"].samples_masked == ("ภาษาไทย",)


def test_sensitive_values_are_detected_and_never_returned_raw() -> None:
    rows = (
        {
            "customer_id": "C-1001",
            "อีเมล": "somchai@example.com",
            "phone": "+66 81 234 5678",
            "client_ip": "192.168.1.10",
        },
        {
            "customer_id": "C-1002",
            "อีเมล": "malee@example.com",
            "phone": "+66 89 999 0000",
            "client_ip": "10.0.0.2",
        },
    )
    result = SchemaProfiler().profile(rows)
    fields = {field.name: field for field in result.fields}
    assert fields["customer_id"].sensitive_category == "identifier"
    assert fields["อีเมล"].sensitive_category == "email"
    assert fields["phone"].sensitive_category == "phone"
    assert fields["client_ip"].sensitive_category == "ip_address"
    serialized = result.model_dump_json()
    for raw in ("C-1001", "somchai@example.com", "+66 81 234 5678", "192.168.1.10"):
        assert raw not in serialized
    assert all(field.pii_classification is PiiClassification.POSSIBLE for field in fields.values())


def test_native_types_json_all_null_and_sampling_bounds() -> None:
    rows = tuple(
        {
            "id": index,
            "when": date(2026, 1, min(index + 1, 28)),
            "payload": {"x": index},
            "nil": None,
        }
        for index in range(20)
    )
    result = SchemaProfiler(max_sample_rows=5).profile(rows, total_rows=100)
    fields = {field.name: field for field in result.fields}
    assert result.sampled_rows == 5 and result.row_count == 100 and result.truncated
    assert fields["id"].inferred_type is DataType.INTEGER
    assert fields["when"].inferred_type is DataType.DATE
    assert fields["payload"].inferred_type is DataType.JSON
    assert fields["nil"].inferred_type is DataType.STRING
    assert fields["nil"].confidence == 0


def test_confirmed_schema_allows_type_override_but_rejects_duplicate_names() -> None:
    field = ConfirmedField(
        name="amount",
        inferred_type=DataType.STRING,
        confirmed_type=DataType.DECIMAL,
        nullable=True,
        required=True,
        confidence=0.8,
        null_percentage=10,
    )
    assert SchemaConfirmation(fields=(field,)).fields[0].confirmed_type is DataType.DECIMAL
    with pytest.raises(ValidationError, match="unique"):
        SchemaConfirmation(fields=(field, field))
