"""Deterministic schema inference, quality metrics, and sample masking."""

from __future__ import annotations

import ipaddress
import json
import math
import re
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pae.domain.enums import DataType, PiiClassification
from pae.profiling.models import ProfileField, ProfilingResult, SensitiveCategory

_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PHONE = re.compile(r"^\+?[0-9][0-9 ()-]{7,18}$")
_CREDIT_CARD = re.compile(r"^(?:\d[ -]?){13,19}$")
_NATIONAL_ID = re.compile(r"^\d{13}$")
_NAME_HINTS: dict[SensitiveCategory, tuple[str, ...]] = {
    "email": ("email", "e_mail", "อีเมล"),
    "phone": ("phone", "mobile", "telephone", "โทรศัพท์", "เบอร์"),
    "national_id": ("national_id", "citizen_id", "เลขบัตร", "บัตรประชาชน"),
    "credit_card": ("credit_card", "card_number", "เลขบัตรเครดิต"),
    "ip_address": ("ip_address", "client_ip", "ip"),
}


class SchemaProfiler:
    def __init__(self, *, max_sample_rows: int = 10_000, max_sample_values: int = 5) -> None:
        self.max_sample_rows = max_sample_rows
        self.max_sample_values = max_sample_values

    def profile(
        self, rows: Sequence[Mapping[str, Any]], *, total_rows: int | None = None
    ) -> ProfilingResult:
        sampled = list(rows[: self.max_sample_rows])
        names = list(dict.fromkeys(name for row in sampled for name in row))
        fields = tuple(self._field(name, sampled) for name in names)
        known_total = total_rows if total_rows is not None else len(rows)
        return ProfilingResult(
            row_count=known_total,
            sampled_rows=len(sampled),
            truncated=known_total > len(sampled) or len(rows) > len(sampled),
            fields=fields,
            warnings=("No fields were found in the sampled rows.",) if not fields else (),
        )

    def _field(self, name: str, rows: Sequence[Mapping[str, Any]]) -> ProfileField:
        present = sum(name in row for row in rows)
        values = [row.get(name) for row in rows if name in row]
        non_null = [value for value in values if value is not None and value != ""]
        null_count = len(rows) - len(non_null)
        typed = [self._value_type(value) for value in non_null]
        counts = Counter(data_type for data_type, _ in typed)
        observed = tuple(sorted(counts, key=lambda item: item.value))
        inferred = counts.most_common(1)[0][0] if counts else DataType.STRING
        mixed = len(observed) > 1
        confidence = (counts[inferred] / len(non_null)) if non_null else 0.0
        detected_format = self._common_format(typed, inferred)
        category = self._sensitive_category(name, non_null)
        pii = PiiClassification.POSSIBLE if category else PiiClassification.NONE
        distinct = len({self._canonical(value) for value in non_null})
        minimum, maximum = self._range(non_null, inferred, category)
        samples = tuple(
            self._display(value, category)
            for value in self._unique_values(non_null)[: self.max_sample_values]
        )
        return ProfileField(
            name=name,
            inferred_type=inferred,
            observed_types=observed,
            mixed_types=mixed,
            nullable=null_count > 0,
            required=present == len(rows),
            null_count=null_count,
            null_percentage=(null_count / len(rows) * 100) if rows else 0,
            distinct_count=distinct,
            minimum=minimum,
            maximum=maximum,
            detected_format=detected_format,
            samples_masked=samples,
            confidence=confidence,
            pii_classification=pii,
            sensitive_category=category,
        )

    @staticmethod
    def _value_type(value: Any) -> tuple[DataType, str | None]:
        if isinstance(value, bool):
            return DataType.BOOLEAN, None
        if isinstance(value, int):
            return DataType.INTEGER, None
        if isinstance(value, (float, Decimal)) and not (
            isinstance(value, float) and math.isnan(value)
        ):
            return DataType.DECIMAL, None
        if isinstance(value, datetime):
            return DataType.DATETIME, "iso-8601"
        if isinstance(value, date):
            return DataType.DATE, "iso-8601-date"
        if isinstance(value, (dict, list)):
            return DataType.JSON, None
        text = str(value).strip()
        lowered = text.lower()
        if lowered in {"true", "false", "yes", "no"}:
            return DataType.BOOLEAN, None
        if re.fullmatch(r"[+-]?(0|[1-9]\d*)", text):
            return DataType.INTEGER, None
        try:
            if text and Decimal(text).is_finite():
                return DataType.DECIMAL, None
        except InvalidOperation:
            pass
        try:
            if "T" in text or " " in text:
                datetime.fromisoformat(text.replace("Z", "+00:00"))
                return DataType.DATETIME, "iso-8601"
        except ValueError:
            pass
        for pattern, format_name, parser in (
            (r"\d{4}-\d{2}-\d{2}", "yyyy-mm-dd", "%Y-%m-%d"),
            (r"\d{2}/\d{2}/\d{4}", "dd/mm/yyyy", "%d/%m/%Y"),
            (r"\d{2}-\d{2}-\d{4}", "dd-mm-yyyy", "%d-%m-%Y"),
        ):
            if re.fullmatch(pattern, text):
                try:
                    datetime.strptime(text, parser)
                    return DataType.DATE, format_name
                except ValueError:
                    pass
        return DataType.STRING, None

    @staticmethod
    def _common_format(
        typed: Sequence[tuple[DataType, str | None]], inferred: DataType
    ) -> str | None:
        formats = [fmt for data_type, fmt in typed if data_type is inferred and fmt]
        return Counter(formats).most_common(1)[0][0] if formats else None

    @staticmethod
    def _canonical(value: Any) -> str:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)

    @classmethod
    def _sensitive_category(cls, name: str, values: Sequence[Any]) -> SensitiveCategory | None:
        lowered = name.lower()
        if lowered == "id" or lowered.endswith("_id"):
            return "identifier"
        for category, hints in _NAME_HINTS.items():
            if any(hint in lowered for hint in hints):
                return category
        text_values = [str(value).strip() for value in values[:20]]
        detectors: tuple[tuple[SensitiveCategory, Callable[[str], bool]], ...] = (
            ("email", lambda value: bool(_EMAIL.fullmatch(value))),
            ("credit_card", lambda value: bool(_CREDIT_CARD.fullmatch(value))),
            ("national_id", lambda value: bool(_NATIONAL_ID.fullmatch(value))),
            ("phone", lambda value: bool(_PHONE.fullmatch(value))),
            ("ip_address", cls._is_ip),
        )
        for category, detector in detectors:
            if (
                text_values
                and sum(detector(value) for value in text_values) / len(text_values) >= 0.8
            ):
                return category
        return None

    @staticmethod
    def _is_ip(value: str) -> bool:
        try:
            ipaddress.ip_address(value)
            return True
        except ValueError:
            return False

    @staticmethod
    def _unique_values(values: Sequence[Any]) -> list[Any]:
        result: list[Any] = []
        seen: set[str] = set()
        for value in values:
            key = SchemaProfiler._canonical(value)
            if key not in seen:
                seen.add(key)
                result.append(value)
        return result

    @staticmethod
    def _display(value: Any, category: SensitiveCategory | None) -> str:
        text = SchemaProfiler._canonical(value) if isinstance(value, (dict, list)) else str(value)
        if not category:
            return text[:100]
        if category == "email" and "@" in text:
            local, domain = text.split("@", 1)
            return f"{local[:1]}***@{domain}"
        if category in {"phone", "national_id", "credit_card"}:
            digits = re.sub(r"\D", "", text)
            return f"***{digits[-4:]}"
        if category == "ip_address":
            return "***.***.***.***"
        if category == "identifier":
            return f"***{text[-1:]}"
        return "***"

    @staticmethod
    def _range(
        values: Sequence[Any], inferred: DataType, category: SensitiveCategory | None
    ) -> tuple[str | int | float | None, str | int | float | None]:
        if (
            not values
            or category
            or inferred
            not in {
                DataType.INTEGER,
                DataType.DECIMAL,
                DataType.DATE,
                DataType.DATETIME,
            }
        ):
            return None, None
        comparable: list[int | float | Decimal | date | datetime] = []
        for value in values:
            data_type, detected_format = SchemaProfiler._value_type(value)
            if data_type is not inferred:
                continue
            if isinstance(value, (int, float, Decimal, date, datetime)) and not isinstance(
                value, bool
            ):
                comparable.append(value)
            elif inferred is DataType.INTEGER:
                comparable.append(int(str(value)))
            elif inferred is DataType.DECIMAL:
                comparable.append(Decimal(str(value)))
            elif inferred in {DataType.DATE, DataType.DATETIME}:
                text = str(value).replace("Z", "+00:00")
                if inferred is DataType.DATETIME:
                    comparable.append(datetime.fromisoformat(text))
                elif detected_format == "dd/mm/yyyy":
                    comparable.append(datetime.strptime(text, "%d/%m/%Y").date())
                elif detected_format == "dd-mm-yyyy":
                    comparable.append(datetime.strptime(text, "%d-%m-%Y").date())
                else:
                    comparable.append(date.fromisoformat(text))
        if not comparable:
            return None, None
        low, high = min(comparable), max(comparable)
        if isinstance(low, Decimal) and isinstance(high, Decimal):
            return float(low), float(high)
        if isinstance(low, (date, datetime)) and isinstance(high, (date, datetime)):
            return low.isoformat(), high.isoformat()
        if isinstance(low, (int, float)) and isinstance(high, (int, float)):
            return low, high
        return None, None
