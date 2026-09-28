"""Development-only user interface for validating the proposed PAE workflow."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from pae.config import Settings


@dataclass(frozen=True)
class FieldProfile:
    """Synthetic field profile shown in the prototype."""

    name: str
    inferred_type: str
    output_name: str
    output_type: str
    null_rate: str
    confidence: str
    example: str
    recommendation: str
    recommendation_reason: str
    selected: bool
    warning: str = ""


@dataclass(frozen=True)
class TransformationRule:
    """Synthetic transformation rule shown in the prototype."""

    title: str
    description: str
    state: str


FIELDS = (
    FieldProfile(
        "cust_id",
        "String",
        "customer_id",
        "String",
        "0%",
        "99%",
        "C-1001",
        "Recommended",
        "ค่าไม่ซ้ำสูง เหมาะเป็นรหัสอ้างอิง",
        True,
    ),
    FieldProfile(
        "amount",
        "String",
        "total_amount",
        "Decimal",
        "0%",
        "91%",
        '"12,450.00"',
        "Recommended",
        "ข้อมูลเชิงตัวเลขที่ใช้คำนวณได้",
        True,
        "พบตัวเลขที่มี comma",
    ),
    FieldProfile(
        "created_at",
        "Date",
        "transaction_date",
        "Date",
        "0%",
        "84%",
        "26/09/2026",
        "Recommended",
        "ใช้กำหนดช่วงเวลาและเรียงลำดับ",
        True,
        "พบวันที่มากกว่า 1 รูปแบบ",
    ),
    FieldProfile(
        "status",
        "String",
        "status",
        "String",
        "0%",
        "99%",
        "ACTIVE",
        "Recommended",
        "มีจำนวนกลุ่มน้อย เหมาะกับการกรอง",
        True,
    ),
    FieldProfile(
        "email",
        "String",
        "email_masked",
        "String",
        "20%",
        "97%",
        "s***@example.com",
        "Review",
        "อาจจำเป็นต่อ output แต่เป็นข้อมูลส่วนบุคคล",
        True,
        "อาจเป็นข้อมูลส่วนบุคคล",
    ),
    FieldProfile(
        "notes",
        "String",
        "notes",
        "String",
        "75%",
        "88%",
        "imported by team-a",
        "Exclude",
        "ค่าไม่สม่ำเสมอและไม่เกี่ยวกับผลลัพธ์หลัก",
        False,
    ),
)

RULES = (
    TransformationRule("กรองสถานะ", "เก็บเฉพาะรายการที่ status = ACTIVE", "Confirmed"),
    TransformationRule("เปลี่ยนชื่อ", "cust_id → customer_id", "Confirmed"),
    TransformationRule("แปลงยอดเงิน", "ลบ comma และแปลง amount เป็น Decimal", "Suggested"),
    TransformationRule("ปกปิดอีเมล", "แสดงเฉพาะอักษรตัวแรกและ domain", "Suggested"),
    TransformationRule("ตัดรายการซ้ำ", "ใช้ customer_id + transaction_date", "Needs review"),
)

SOURCE_ROWS = (
    ("C-1001", "12,450.00", "26/09/2026", "ACTIVE", "s***@example.com", "team-a"),
    ("C-1002", "8,900.50", "2026-09-25", "ACTIVE", "n***@example.com", "—"),
    ("C-1002", "8,900.50", "2026-09-25", "ACTIVE", "n***@example.com", "retry"),
    ("C-1003", "1,250", "24/09/2026", "INACTIVE", "—", "—"),
)

OUTPUT_ROWS = (
    ("C-1001", "12450.00", "2026-09-26", "s***@example.com"),
    ("C-1002", "8900.50", "2026-09-25", "n***@example.com"),
)

PYTHON_PREVIEW = """from decimal import Decimal


def transform(row: dict[str, str]) -> dict[str, object] | None:
    if row["status"] != "ACTIVE":
        return None
    return {
        "customer_id": row["cust_id"].strip(),
        "total_amount": Decimal(row["amount"].replace(",", "")),
        "transaction_date": normalize_date(row["created_at"]),
        "email_masked": mask_email(row.get("email")),
    }
"""

README_PREVIEW = """# Customer Active Transactions

Prototype package generated from a confirmed mock specification.

## Input
Synthetic CSV with customer transactions.

## Run
`python src/pipeline.py --input sample.csv --output output.csv`

> Prototype only — review generated code before production use.
"""


def _build_mock_archive() -> BytesIO:
    """Build a deterministic, secret-free package for testing the download flow."""

    specification = {
        "name": "customer-active-transactions",
        "prototype": True,
        "source": {"type": "synthetic_csv", "contains_real_data": False},
        "fields": [asdict(field) for field in FIELDS],
        "rules": [asdict(rule) for rule in RULES],
        "target": {"language": "python", "output": "csv"},
    }
    manifest = {
        "artifact_status": "prototype_mock",
        "safe_for_production": False,
        "contains_credentials": False,
        "contains_source_sample": False,
    }

    archive = BytesIO()
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as package:
        package.writestr("README.md", README_PREVIEW)
        package.writestr("src/pipeline.py", PYTHON_PREVIEW)
        package.writestr(
            "pipeline-spec.json", json.dumps(specification, ensure_ascii=False, indent=2)
        )
        package.writestr("artifact-manifest.json", json.dumps(manifest, indent=2))
    archive.seek(0)
    return archive


def create_ui_router(settings: Settings) -> APIRouter:
    """Create prototype routes only after the environment gate has passed."""

    router = APIRouter(include_in_schema=False)
    templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")

    @router.get("/ui", response_class=HTMLResponse)
    def prototype_ui(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="ui.html",
            context={
                "app_name": settings.app_name,
                "environment": settings.environment,
                "fields": FIELDS,
                "rules": RULES,
                "source_rows": SOURCE_ROWS,
                "output_rows": OUTPUT_ROWS,
                "python_preview": PYTHON_PREVIEW,
                "readme_preview": README_PREVIEW,
            },
        )

    @router.get("/ui/mock-export")
    def mock_export() -> StreamingResponse:
        return StreamingResponse(
            _build_mock_archive(),
            media_type="application/zip",
            headers={
                "Content-Disposition": (
                    'attachment; filename="pae-prototype-customer-transactions.zip"'
                ),
                "X-PAE-Artifact-Status": "prototype-mock",
            },
        )

    return router
