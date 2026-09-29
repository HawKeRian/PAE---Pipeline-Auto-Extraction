"""Secure ingestion tests for every MVP file format and failure mode."""

from __future__ import annotations

import io
import os
import zipfile
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import openpyxl
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pydantic import ValidationError

from pae.domain.enums import DataType
from pae.ingestion.models import IngestionOptions
from pae.ingestion.service import FileIngestionService
from pae.persistence.errors import (
    EncodingInvalid,
    FileContentInvalid,
    FileTypeUnsupported,
    IngestionLimitExceeded,
    SheetSelectionRequired,
    UnsafeUpload,
    UploadTooLarge,
)


@pytest.fixture
def service(tmp_path: Path) -> FileIngestionService:
    return FileIngestionService(
        tmp_path / "samples",
        max_file_bytes=1_000_000,
        max_sample_rows=3,
        max_columns=10,
        retention_hours=1,
    )


def xlsx_bytes(*, multiple_sheets: bool = False) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Orders"
    sheet.append(["order_id", "amount", "formula_text"])
    sheet.append(["A-1", 10.5, "=1+1"])
    if multiple_sheets:
        workbook.create_sheet("Archive")
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def parquet_bytes() -> bytes:
    table = pa.table({"order_id": ["A-1", "A-2"], "amount": [10.5, 20.0]})
    output = pa.BufferOutputStream()
    pq.write_table(table, output)
    return output.getvalue().to_pybytes()


def test_csv_delimiter_encoding_limits_and_reusable_pattern(
    service: FileIngestionService,
) -> None:
    source = "name;amount\nกิตติ;10\nมาลี;20\n".encode("cp874")
    stored = service.ingest(
        "customers.csv",
        source,
        "text/csv",
        IngestionOptions(encoding="cp874", delimiter=";"),
    )
    metadata = stored.analysis.metadata
    assert metadata.file_format == "csv"
    assert metadata.encoding == "cp874"
    assert metadata.delimiter == ";"
    assert [column.name for column in metadata.columns] == ["name", "amount"]
    assert metadata.columns[1].inferred_type == "integer"
    assert stored.analysis.runtime.filename_pattern == "*.csv"
    assert "customers.csv" not in stored.analysis.runtime.filename_pattern
    assert (service.storage_root / stored.storage_ref).read_bytes() == source


def test_json_and_json_lines_detect_optional_columns(service: FileIngestionService) -> None:
    json_result = service.ingest(
        "orders.json",
        b'[{"id": 1, "note": "a"}, {"id": 2}]',
        "application/json",
        IngestionOptions(),
    )
    profiles = {column.name: column for column in json_result.analysis.metadata.columns}
    assert profiles["id"].required is True
    assert profiles["id"].inferred_type == "integer"
    assert profiles["note"].required is False
    assert json_result.analysis.runtime.optional_columns == ("note",)

    jsonl_result = service.ingest(
        "orders.jsonl",
        b'{"id": 1}\n{"id": 2}\n',
        "application/x-ndjson",
        IngestionOptions(),
    )
    assert jsonl_result.analysis.metadata.file_format == "json_lines"
    assert jsonl_result.analysis.metadata.total_rows == 2


def test_excel_requires_sheet_selection_and_treats_formula_as_data(
    service: FileIngestionService,
) -> None:
    content = xlsx_bytes(multiple_sheets=True)
    with pytest.raises(SheetSelectionRequired) as captured:
        service.ingest(
            "orders.xlsx",
            content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            IngestionOptions(),
        )
    assert captured.value.details["available_sheets"] == ["Orders", "Archive"]

    stored = service.ingest(
        "orders.xlsx",
        content,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        IngestionOptions(sheet_name="Orders"),
    )
    assert stored.analysis.metadata.sheet_name == "Orders"
    columns = {column.name: column for column in stored.analysis.metadata.columns}
    assert columns["formula_text"].inferred_type == "string"


def test_excel_inspection_summarizes_all_sheets_without_values(
    service: FileIngestionService,
) -> None:
    content = xlsx_bytes(multiple_sheets=True)
    inspection = service.inspect_workbook(
        "orders.xlsx",
        content,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    assert [sheet.name for sheet in inspection.sheets] == ["Orders", "Archive"]
    assert inspection.sheets[0].status == "ready"
    assert inspection.sheets[0].columns == ("order_id", "amount", "formula_text")
    assert inspection.sheets[1].status == "empty"
    assert "A-1" not in inspection.model_dump_json()


def test_parquet_signature_and_rows(service: FileIngestionService) -> None:
    stored = service.ingest(
        "orders.parquet",
        parquet_bytes(),
        "application/vnd.apache.parquet",
        IngestionOptions(),
    )
    assert stored.analysis.metadata.file_format == "parquet"
    assert stored.analysis.metadata.total_rows == 2
    assert stored.analysis.metadata.columns[1].inferred_type == "decimal"
    with pytest.raises(FileContentInvalid, match="signature"):
        service.ingest(
            "fake.parquet", b"not parquet", "application/octet-stream", IngestionOptions()
        )


@pytest.mark.parametrize("filename", ["../orders.csv", "folder/orders.csv", "C:\\orders.csv"])
def test_path_traversal_is_rejected(service: FileIngestionService, filename: str) -> None:
    with pytest.raises(UnsafeUpload):
        service.ingest(filename, b"id\n1\n", "text/csv", IngestionOptions())


def test_size_mime_extension_archive_and_column_controls(tmp_path: Path) -> None:
    service = FileIngestionService(tmp_path / "samples", max_file_bytes=100, max_columns=2)
    with pytest.raises(UploadTooLarge):
        service.ingest("large.csv", b"x" * 101, "text/csv", IngestionOptions())
    with pytest.raises(FileTypeUnsupported):
        service.ingest("image.png", b"not-image", "image/png", IngestionOptions())
    with pytest.raises(FileTypeUnsupported, match="content type"):
        service.ingest("orders.csv", b"id\n1", "image/png", IngestionOptions())
    with pytest.raises(IngestionLimitExceeded):
        service.ingest("wide.csv", b"a,b,c\n1,2,3", "text/csv", IngestionOptions())
    with pytest.raises(FileTypeUnsupported, match="JSON"):
        service.ingest("wrong.csv", b'[{"id": 1}]', "text/csv", IngestionOptions())
    signature_service = FileIngestionService(
        tmp_path / "signature-samples", max_file_bytes=1_000_000, max_columns=2
    )
    with pytest.raises(FileTypeUnsupported, match="Parquet"):
        signature_service.ingest("wrong.csv", parquet_bytes(), "text/csv", IngestionOptions())

    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("data.csv", "id\n1")
    archive_service = FileIngestionService(
        tmp_path / "archive-samples", max_file_bytes=1_000, max_columns=2
    )
    with pytest.raises(UnsafeUpload, match="Archive"):
        archive_service.ingest("archive.csv", archive.getvalue(), "text/csv", IngestionOptions())


def test_unsafe_or_invalid_xlsx_archive_is_rejected(service: FileIngestionService) -> None:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("[Content_Types].xml", "types")
        zipped.writestr("xl/workbook.xml", "workbook")
        zipped.writestr("../escape.xml", "unsafe")
    with pytest.raises(UnsafeUpload, match="unsafe archive path"):
        service.ingest(
            "unsafe.xlsx",
            archive.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            IngestionOptions(),
        )

    with pytest.raises(FileContentInvalid, match="XLSX"):
        service.ingest(
            "corrupt.xlsx",
            b"PK-not-a-zip",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            IngestionOptions(),
        )


def test_invalid_encoding_json_shape_schema_and_csv_rows(service: FileIngestionService) -> None:
    with pytest.raises(EncodingInvalid):
        service.ingest("bad.csv", b"name\n\xff", "text/csv", IngestionOptions(encoding="utf-8"))
    with pytest.raises(FileContentInvalid, match="JSON is invalid"):
        service.ingest("bad.json", b"{broken", "application/json", IngestionOptions())
    with pytest.raises(FileContentInvalid, match="Record 1"):
        service.ingest("array.json", b"[1, 2]", "application/json", IngestionOptions())
    with pytest.raises(FileContentInvalid, match="row 2"):
        service.ingest(
            "bad.jsonl", b'{"id": 1}\nnot-json', "application/x-ndjson", IngestionOptions()
        )
    with pytest.raises(FileContentInvalid, match="more values"):
        service.ingest("bad.csv", b"a,b\n1,2,3", "text/csv", IngestionOptions())
    inconsistent = service.ingest("optional.csv", b"a,b\n1,2\n3", "text/csv", IngestionOptions())
    assert inconsistent.analysis.runtime.optional_columns == ("b",)


def test_row_limit_and_retention_cleanup(service: FileIngestionService) -> None:
    original = b"id\n1\n2\n3\n4\n"
    stored = service.ingest(
        "bounded.csv", original, "text/csv", IngestionOptions(sample_row_limit=2)
    )
    assert stored.analysis.metadata.sampled_rows == 2
    assert stored.analysis.metadata.truncated is True
    target = service.storage_root / stored.storage_ref
    old = (datetime.now(UTC) - timedelta(hours=2)).timestamp()
    os.utime(target, (old, old))
    assert service.cleanup_expired() == 1
    assert not target.exists()


def test_custom_runtime_pattern_is_validated(service: FileIngestionService) -> None:
    stored = service.ingest(
        "orders.csv",
        b"id\n1",
        "text/csv",
        IngestionOptions(filename_pattern="incoming-*.csv"),
    )
    assert stored.analysis.runtime.filename_pattern == "incoming-*.csv"
    with pytest.raises(ValueError, match="relative glob"):
        service.ingest(
            "orders.csv",
            b"id\n1",
            "text/csv",
            IngestionOptions(filename_pattern="../*.csv"),
        )


def test_options_empty_files_headers_and_empty_objects_are_rejected(
    service: FileIngestionService,
) -> None:
    with pytest.raises(ValidationError, match="delimiter must contain exactly one character"):
        IngestionOptions(delimiter="||")
    with pytest.raises(FileContentInvalid, match="empty"):
        service.ingest("empty.csv", b"", "text/csv", IngestionOptions())
    with pytest.raises(FileContentInvalid, match="header row"):
        service.ingest("no-header.csv", b"\n", "text/csv", IngestionOptions())
    with pytest.raises(FileContentInvalid, match="cannot be empty"):
        service.ingest("empty-header.csv", b"id,\n1,2", "text/csv", IngestionOptions())
    with pytest.raises(FileContentInvalid, match="unique"):
        service.ingest("duplicate.csv", b"id,id\n1,2", "text/csv", IngestionOptions())
    with pytest.raises(FileContentInvalid, match="No columns"):
        service.ingest("empty-object.json", b"{}", "application/json", IngestionOptions())


def test_json_column_limit_is_enforced_after_profiling(tmp_path: Path) -> None:
    bounded = FileIngestionService(tmp_path / "samples", max_columns=2)
    with pytest.raises(IngestionLimitExceeded, match="3 columns"):
        bounded.ingest(
            "wide.json",
            b'{"a": 1, "b": 2, "c": 3}',
            "application/json",
            IngestionOptions(),
        )


def test_excel_signature_missing_sheet_and_row_limit(
    tmp_path: Path, service: FileIngestionService
) -> None:
    with pytest.raises(FileContentInvalid, match="signature"):
        service.ingest(
            "not-excel.xlsx",
            b"not-a-workbook",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            IngestionOptions(),
        )
    content = xlsx_bytes()
    with pytest.raises(SheetSelectionRequired, match="does not exist"):
        service.ingest(
            "orders.xlsx",
            content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            IngestionOptions(sheet_name="Missing"),
        )

    bounded = FileIngestionService(tmp_path / "excel-samples", max_sample_rows=1)
    stored = bounded.ingest(
        "orders.xlsx",
        content,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        IngestionOptions(sample_row_limit=1),
    )
    assert stored.analysis.metadata.sampled_rows == 1


def test_archive_resource_guards_and_invalid_workbook(tmp_path: Path) -> None:
    def fake_workbook(*entries: tuple[str, str]) -> bytes:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
            for name, value in entries:
                zipped.writestr(name, value)
        return output.getvalue()

    required = (("[Content_Types].xml", "types"), ("xl/workbook.xml", "workbook"))
    too_many = FileIngestionService(tmp_path / "entries", max_archive_entries=1)
    with pytest.raises(UnsafeUpload, match="too many"):
        too_many.ingest(
            "many.xlsx",
            fake_workbook(*required),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            IngestionOptions(),
        )

    too_large = FileIngestionService(tmp_path / "expanded", max_archive_uncompressed_bytes=4)
    with pytest.raises(UnsafeUpload, match="expands beyond"):
        too_large.ingest(
            "large.xlsx",
            fake_workbook(*required),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            IngestionOptions(),
        )

    suspicious = FileIngestionService(tmp_path / "ratio")
    with pytest.raises(UnsafeUpload, match="compression ratio"):
        suspicious.ingest(
            "compressed.xlsx",
            fake_workbook(("[Content_Types].xml", "x" * 20_000), required[1]),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            IngestionOptions(),
        )

    invalid = FileIngestionService(tmp_path / "invalid")
    with pytest.raises(FileContentInvalid, match="not a valid XLSX"):
        invalid.ingest(
            "invalid.xlsx",
            fake_workbook(("readme.txt", "not a workbook")),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            IngestionOptions(),
        )


def test_json_lines_and_parquet_sampling_are_bounded(tmp_path: Path) -> None:
    bounded = FileIngestionService(tmp_path / "samples", max_sample_rows=1)
    jsonl = bounded.ingest(
        "rows.jsonl",
        b'\n{"id": 1}\n{"id": 2}\n',
        "application/x-ndjson",
        IngestionOptions(sample_row_limit=1),
    )
    assert jsonl.analysis.metadata.sampled_rows == 1
    assert jsonl.analysis.metadata.truncated is True
    parquet = bounded.ingest(
        "rows.parquet",
        parquet_bytes(),
        "application/vnd.apache.parquet",
        IngestionOptions(sample_row_limit=1),
    )
    assert parquet.analysis.metadata.sampled_rows == 1
    assert parquet.analysis.metadata.truncated is True

    with pytest.raises(FileContentInvalid, match="could not be read"):
        bounded.ingest(
            "broken.parquet",
            b"PAR1brokenPAR1",
            "application/vnd.apache.parquet",
            IngestionOptions(),
        )


def test_discard_cleanup_and_storage_reference_safety(
    tmp_path: Path, service: FileIngestionService
) -> None:
    assert service.cleanup_expired() == 0
    stored = service.ingest("orders.csv", b"id\n1", None, IngestionOptions())
    target = service.storage_root / stored.storage_ref
    assert stored.analysis.metadata.content_type == "application/octet-stream"
    service.discard(stored.storage_ref)
    assert not target.exists()
    service.discard(stored.storage_ref)
    with pytest.raises(UnsafeUpload, match="reference is invalid"):
        service.discard("../outside.csv")

    service.storage_root.mkdir(parents=True, exist_ok=True)
    directory = service.storage_root / "keep-directory"
    directory.mkdir()
    fresh = service.storage_root / "fresh.csv"
    fresh.write_bytes(b"id\n1")
    assert service.cleanup_expired(now=datetime.now(UTC)) == 0
    assert directory.exists() and fresh.exists()


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([], DataType.STRING),
        ([True, False], DataType.BOOLEAN),
        ([datetime(2026, 1, 1, tzinfo=UTC)], DataType.DATETIME),
        ([date(2026, 1, 1)], DataType.DATE),
        ([{"nested": 1}, [1, 2]], DataType.JSON),
        (["true", "FALSE"], DataType.BOOLEAN),
        (["10.5", "20.0"], DataType.DECIMAL),
        (["2026-01-01T12:30:00+00:00"], DataType.DATETIME),
        (["2026-01-01"], DataType.DATE),
        (["not-a-date", "text"], DataType.STRING),
        ([Decimal("NaN")], DataType.DECIMAL),
    ],
)
def test_type_inference(values: list[object], expected: DataType) -> None:
    assert FileIngestionService._infer_type(values) == expected


def test_excel_inspection_reports_corrupt_workbook(service: FileIngestionService) -> None:
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as archive:
        archive.writestr("[Content_Types].xml", "invalid XML")
        archive.writestr("xl/workbook.xml", "invalid XML")
    with pytest.raises(FileContentInvalid):
        service.inspect_workbook("broken.xlsx", content.getvalue(), None)
