"""Shared deterministic transformation semantics for preview and generated Python packages.

This module intentionally uses only the Python standard library so it can be copied verbatim into
a generated standalone package.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _cast(value: Any, target: str, parameters: dict[str, Any]) -> Any:
    if value is None:
        return None
    if target == "string":
        return str(value)
    if target == "integer":
        return int(str(value))
    if target == "decimal":
        text = str(value)
        thousands = parameters.get("thousands_separator")
        decimal_separator = parameters.get("decimal_separator", ".")
        if thousands:
            text = text.replace(str(thousands), "")
        if decimal_separator != ".":
            text = text.replace(str(decimal_separator), ".")
        result = Decimal(text)
        if not result.is_finite():
            raise ValueError("decimal value must be finite")
        return result
    if target == "boolean":
        if isinstance(value, bool):
            return value
        lowered = str(value).strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
        raise ValueError("boolean value is invalid")
    if target in {"date", "datetime"}:
        text = str(value).replace("Z", "+00:00")
        formats = parameters.get("formats", [])
        if formats:
            for item in formats:
                try:
                    parsed = datetime.strptime(text, str(item))
                    return parsed.date() if target == "date" else parsed
                except ValueError:
                    continue
            raise ValueError("date value does not match confirmed formats")
        return date.fromisoformat(text) if target == "date" else datetime.fromisoformat(text)
    if target == "json":
        return value if isinstance(value, (dict, list)) else json.loads(str(value))
    raise ValueError(f"unsupported cast target: {target}")


def _compare(value: Any, operator: str, expected: Any) -> bool:
    if operator == "is_null":
        return value is None
    if operator == "not_null":
        return value is not None
    if operator == "eq":
        return bool(value == expected)
    if operator == "ne":
        return bool(value != expected)
    if value is None:
        return False
    if operator == "gt":
        return bool(value > expected)
    if operator == "gte":
        return bool(value >= expected)
    if operator == "lt":
        return bool(value < expected)
    if operator == "lte":
        return bool(value <= expected)
    if operator == "contains":
        return str(expected) in str(value)
    if operator == "in":
        return value in expected
    raise ValueError(f"unsupported filter operator: {operator}")


def _mask(value: Any, strategy: str) -> Any:
    if value is None:
        return None
    text = str(value)
    if strategy == "email":
        if "@" not in text:
            return "***"
        local, domain = text.split("@", 1)
        return f"{local[:1]}***@{domain}"
    if strategy == "last4":
        return f"***{text[-4:]}"
    if strategy == "hash":
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    if strategy == "redact":
        return "***"
    raise ValueError(f"unsupported masking strategy: {strategy}")


def _derive(row: dict[str, Any], inputs: list[str], parameters: dict[str, Any]) -> Any:
    operation = parameters.get("operation")
    values = [row.get(name) for name in inputs]
    if operation == "concat":
        separator = str(parameters.get("separator", ""))
        return separator.join("" if value is None else str(value) for value in values)
    if operation == "coalesce":
        return next((value for value in values if value is not None), parameters.get("default"))
    if len(values) != 2:
        raise ValueError("arithmetic derive operations require exactly two inputs")
    left, right = values
    if left is None or right is None:
        raise ValueError("arithmetic derive inputs cannot be null")
    if operation == "add":
        return left + right
    if operation == "subtract":
        return left - right
    if operation == "multiply":
        return left * right
    if operation == "divide":
        return left / right
    raise ValueError(f"unsupported derive operation: {operation}")


def _aggregate(rows: list[dict[str, Any]], rule: dict[str, Any]) -> list[dict[str, Any]]:
    parameters = rule["parameters"]
    group_by = [str(item) for item in parameters.get("group_by", [])]
    function = str(parameters.get("function"))
    input_name = rule["inputs"][0]
    output = rule.get("output") or f"{function}_{input_name}"
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(tuple(row.get(name) for name in group_by), []).append(row)
    result: list[dict[str, Any]] = []
    for key, members in groups.items():
        values = [value for row in members if (value := row.get(input_name)) is not None]
        if function == "count":
            aggregate: Any = len(members) if parameters.get("count_all", False) else len(values)
        elif function == "sum":
            aggregate = sum(values, Decimal(0))
        elif function == "min":
            aggregate = min(values) if values else None
        elif function == "max":
            aggregate = max(values) if values else None
        elif function == "avg":
            aggregate = sum(values, Decimal(0)) / len(values) if values else None
        else:
            raise ValueError(f"unsupported aggregate function: {function}")
        result.append({**dict(zip(group_by, key, strict=True)), output: aggregate})
    return result


def _validate_rule(rule: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    field = rule["field"]
    kind = rule["kind"]
    parameters = rule.get("parameters", {})
    seen: set[str] = set()
    for index, row in enumerate(rows):
        value = row.get(field)
        valid = True
        if kind == "not_null":
            valid = value is not None
        elif kind == "unique":
            key = json.dumps(_jsonable(value), sort_keys=True)
            valid = value is None or key not in seen
            seen.add(key)
        elif kind == "range":
            valid = value is None or (
                (parameters.get("minimum") is None or value >= parameters["minimum"])
                and (parameters.get("maximum") is None or value <= parameters["maximum"])
            )
        elif kind == "regex":
            valid = value is None or bool(re.fullmatch(str(parameters["pattern"]), str(value)))
        elif kind == "allowed_values":
            valid = value is None or value in parameters.get("values", [])
        if not valid:
            issues.append(
                {
                    "rule_id": rule["rule_id"],
                    "row_index": index,
                    "field": field,
                    "severity": rule.get("severity", "error"),
                    "message": f"{kind} validation failed for {field}",
                }
            )
    return issues


def execute(specification: dict[str, Any], source_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply a specification to rows and return JSON-compatible preview details."""

    rows = [dict(row) for row in source_rows]
    rejected: list[dict[str, Any]] = []
    impacts: list[dict[str, Any]] = []
    for rule in sorted(specification.get("transformations", []), key=lambda item: item["order"]):
        if not rule.get("enabled", True):
            continue
        before = len(rows)
        before_rows = _jsonable([dict(row) for row in rows])
        kind = rule["kind"]
        inputs = list(rule["inputs"])
        parameters = rule.get("parameters", {})
        try:
            if kind == "include":
                rows = [{name: row.get(name) for name in inputs if name in row} for row in rows]
            elif kind == "exclude":
                rows = [
                    {key: value for key, value in row.items() if key not in inputs} for row in rows
                ]
            elif kind == "rename":
                source, output = inputs[0], rule["output"]
                rows = [
                    {output if key == source else key: value for key, value in row.items()}
                    for row in rows
                ]
            elif kind == "cast":
                field = inputs[0]
                kept: list[dict[str, Any]] = []
                for index, row in enumerate(rows):
                    try:
                        row[field] = _cast(row.get(field), str(parameters["type"]), parameters)
                        kept.append(row)
                    except (ValueError, TypeError, InvalidOperation) as exc:
                        rejected.append(
                            {
                                "row_index": index,
                                "rule_id": rule["rule_id"],
                                "reason": str(exc),
                                "row": row,
                            }
                        )
                rows = kept
            elif kind == "filter":
                field = inputs[0]
                rows = [
                    row
                    for row in rows
                    if _compare(
                        row.get(field), str(parameters["operator"]), parameters.get("value")
                    )
                ]
            elif kind == "sort":
                nulls = str(parameters.get("nulls", "last"))
                for field in reversed(inputs):
                    present = [row for row in rows if row.get(field) is not None]
                    missing = [row for row in rows if row.get(field) is None]
                    present.sort(
                        key=lambda row: row[field],
                        reverse=str(parameters.get("direction", "ascending")) == "descending",
                    )
                    rows = missing + present if nulls == "first" else present + missing
            elif kind == "deduplicate":
                keys = [str(item) for item in parameters.get("keys", inputs)]
                survivor = str(parameters.get("survivor", "first"))
                iterable = rows if survivor == "first" else list(reversed(rows))
                seen: set[tuple[Any, ...]] = set()
                unique: list[dict[str, Any]] = []
                for row in iterable:
                    key = tuple(row.get(name) for name in keys)
                    if key not in seen:
                        seen.add(key)
                        unique.append(row)
                rows = unique if survivor == "first" else list(reversed(unique))
            elif kind == "replace":
                field = inputs[0]
                old, new = parameters.get("old"), parameters.get("new")
                for row in rows:
                    if row.get(field) == old:
                        row[field] = new
            elif kind == "handle_null":
                field = inputs[0]
                for row in rows:
                    if row.get(field) is None:
                        row[field] = parameters.get("value")
            elif kind == "derive":
                for row in rows:
                    row[rule["output"]] = _derive(row, inputs, parameters)
            elif kind == "aggregate":
                rows = _aggregate(rows, rule)
            elif kind == "mask":
                field = inputs[0]
                for row in rows:
                    row[field] = _mask(row.get(field), str(parameters.get("strategy", "redact")))
            elif kind == "join":
                raise ValueError("multi-source join is deferred")
            else:
                raise ValueError(f"unsupported transformation kind: {kind}")
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise ValueError(f"rule {rule['rule_id']} failed: {exc}") from exc
        after_rows = _jsonable(rows)
        changed = (
            abs(before - len(rows))
            if before != len(rows)
            else sum(left != right for left, right in zip(before_rows, after_rows, strict=True))
        )
        impacts.append(
            {
                "rule_id": rule["rule_id"],
                "kind": kind,
                "before_count": before,
                "after_count": len(rows),
                "changed_count": changed,
            }
        )

    issues = [
        issue
        for rule in specification.get("validations", [])
        for issue in _validate_rule(rule, rows)
    ]
    rejected_indexes = {issue["row_index"] for issue in issues if issue["severity"] == "error"}
    if rejected_indexes and specification.get("error_policy") == "fail_job":
        raise ValueError("validation failed and error_policy is fail_job")
    validation_rejected = []
    for index, row in enumerate(rows):
        failed = [
            issue
            for issue in issues
            if issue["severity"] == "error" and issue["row_index"] == index
        ]
        if failed:
            validation_rejected.append(
                {
                    "row_index": index,
                    "rule_id": str(failed[0]["rule_id"]),
                    "reason": "; ".join(str(issue["message"]) for issue in failed),
                    "row": row,
                }
            )
    rejected.extend(validation_rejected)
    output = [row for index, row in enumerate(rows) if index not in rejected_indexes]
    sensitive = {
        name
        for field in specification.get("fields", [])
        if field.get("pii_classification", "none") != "none"
        for name in (field.get("source_name"), field.get("target_name"))
        if name
    }
    for item in rejected:
        item["row"] = {
            key: "***" if key in sensitive and value is not None else value
            for key, value in item["row"].items()
        }
    result = _jsonable(
        {
            "output_rows": output,
            "rejected_rows": rejected,
            "issues": issues,
            "rule_impacts": impacts,
            "input_count": len(source_rows),
            "output_count": len(output),
            "rejected_count": len(rejected),
        }
    )
    if not isinstance(result, dict):
        raise TypeError("runtime result must be an object")
    return result
