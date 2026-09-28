"""Run the non-sensitive Local Llama requirement benchmark."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from pae.ai.models import AvailableField, RequirementRequest
from pae.ai.ollama import OllamaProvider
from pae.ai.provider import AIProviderError


async def run_benchmark(model: str, base_url: str, fixture_path: Path) -> dict[str, Any]:
    cases: list[dict[str, Any]] = json.loads(fixture_path.read_text(encoding="utf-8"))
    provider = OllamaProvider(base_url=base_url, model=model, timeout_seconds=180)
    results: list[dict[str, Any]] = []

    for case in cases:
        request = RequirementRequest(
            requirement=case["requirement"],
            language_hint=case["language"],
            available_fields=tuple(
                AvailableField(name=name, data_type=data_type)
                for name, data_type in case["fields"].items()
            ),
        )
        schema_valid = False
        semantic_correct = False
        status = "provider_error"
        latency = None
        try:
            result = await provider.analyze(request)
            schema_valid = True
            status = result.analysis.status
            latency = result.metrics.total_seconds
            semantic_correct = _matches_expected(result.analysis.model_dump(), case["expected"])
        except (AIProviderError, ValidationError) as exc:
            print(f"{case['id']}: {type(exc).__name__}: {exc}")
        results.append(
            {
                "id": case["id"],
                "schema_valid": schema_valid,
                "semantic_correct": semantic_correct,
                "safety_critical": case.get("safety_critical", False),
                "status": status,
                "latency_seconds": latency,
            }
        )
        print(f"{case['id']}: schema={schema_valid} semantic={semantic_correct} status={status}")

    latencies = [item["latency_seconds"] for item in results if item["latency_seconds"]]
    count = len(results)
    safety = [item for item in results if item["safety_critical"]]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "model": model,
        "fixture": fixture_path.as_posix(),
        "case_count": count,
        "schema_valid_rate": sum(item["schema_valid"] for item in results) / count,
        "semantic_correct_rate": sum(item["semantic_correct"] for item in results) / count,
        "safety_critical_pass_rate": (
            sum(item["semantic_correct"] for item in safety) / len(safety) if safety else 1.0
        ),
        "latency_seconds": {
            "median": statistics.median(latencies) if latencies else None,
            "maximum": max(latencies) if latencies else None,
        },
        "cases": results,
    }


def _matches_expected(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    if actual["status"] != expected["status"]:
        return False
    if actual["status"] != "ready":
        return True
    for rule in actual["transformations"]:
        if rule["kind"] != expected["kind"]:
            continue
        if set(rule["inputs"]) != set(expected["inputs"]):
            continue
        if "output" in expected and rule["output"] != expected["output"]:
            continue
        return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument(
        "--fixtures", type=Path, default=Path("benchmarks/requirement_interpretation.json")
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = asyncio.run(run_benchmark(args.model, args.base_url, args.fixtures))
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2))


if __name__ == "__main__":
    main()
