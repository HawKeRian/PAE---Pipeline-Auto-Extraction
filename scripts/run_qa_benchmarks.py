"""Run repeatable local MVP latency/resource benchmarks and emit JSON evidence."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import platform
import statistics
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

import psutil
from fastapi.testclient import TestClient

from pae.config import Settings
from pae.domain.enums import DataType, OutputFormat, TargetLanguage
from pae.domain.models import (
    FieldDefinition,
    FileDiscoveryContract,
    FileSource,
    OutputContract,
    PipelineSpecification,
    TargetRuntime,
)
from pae.generation.python_generator import PythonGenerator
from pae.main import create_app
from pae.preview.service import PreviewService
from pae.profiling.service import SchemaProfiler
from pae.sandbox import SandboxRunner


def percentile(values: list[float], percentage: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * percentage) - 1)]


def measure(function: Callable[[], object], repetitions: int) -> list[float]:
    values = []
    for _ in range(repetitions):
        started = time.perf_counter()
        function()
        values.append(time.perf_counter() - started)
    return values


def specification() -> PipelineSpecification:
    return PipelineSpecification.model_validate(
        {
            "specification_id": "12345678-1234-5678-1234-567812345678",
            "project_id": str(UUID("87654321-4321-8765-4321-876543218765")),
            "revision": 1,
            "name": "qa-benchmark",
            "source_fingerprint": "a" * 64,
            "sources": [
                FileSource(
                    source_id="input",
                    file_format="csv",
                    original_name="sample.csv",
                    runtime=FileDiscoveryContract(filename_pattern="*.csv"),
                ).model_dump(mode="json")
            ],
            "fields": [
                FieldDefinition(
                    source_id="input",
                    source_name="id",
                    target_name="id",
                    inferred_type=DataType.INTEGER,
                    confirmed_type=DataType.INTEGER,
                    nullable=False,
                    confidence=1,
                    null_percentage=0,
                ).model_dump(mode="json")
            ],
            "output": OutputContract(format=OutputFormat.CSV).model_dump(mode="json"),
            "target": TargetRuntime(language=TargetLanguage.PYTHON).model_dump(mode="json"),
            "confirmed_by": "benchmark",
            "confirmed_at": datetime.now(UTC).isoformat(),
        }
    )


async def preview_timings(root: Path, rows: tuple[dict[str, int], ...]) -> list[float]:
    service = PreviewService(SandboxRunner(root, timeout_seconds=10))
    values = []
    for _ in range(5):
        started = time.perf_counter()
        await service.preview(specification(), rows, timeout_seconds=10)
        values.append(time.perf_counter() - started)
    return values


def summarize(values: list[float], threshold: float) -> dict[str, object]:
    p95 = percentile(values, 0.95)
    return {
        "runs": len(values),
        "median_seconds": round(statistics.median(values), 6),
        "p95_seconds": round(p95, 6),
        "maximum_seconds": round(max(values), 6),
        "threshold_seconds": threshold,
        "passed": p95 <= threshold,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    process = psutil.Process()
    rss_before = process.memory_info().rss
    profile_rows = tuple(
        {"id": index, "amount": f"{index % 100}.25", "category": f"c{index % 10}"}
        for index in range(100_000)
    )
    preview_rows = tuple({"id": index} for index in range(10_000))
    profiler = SchemaProfiler(max_sample_rows=100_000)
    profiling = measure(lambda: profiler.profile(profile_rows), 5)
    generation = measure(lambda: PythonGenerator().generate(specification()), 20)
    with TemporaryDirectory(prefix="pae-qa-") as directory:
        root = Path(directory)
        preview = asyncio.run(preview_timings(root / "sandbox", preview_rows))
        app = create_app(
            Settings(
                environment="testing",
                data_dir=root / "data",
                generated_dir=root / "generated",
                structured_logging=False,
            )
        )
        client = TestClient(app)
        health = measure(lambda: client.get("/health").raise_for_status(), 100)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "reference_machine": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_logical": psutil.cpu_count(),
            "memory_total_bytes": psutil.virtual_memory().total,
        },
        "workloads": {
            "profiling_100000_rows": summarize(profiling, 60),
            "preview_10000_rows": summarize(preview, 5),
            "python_generation": summarize(generation, 60),
            "health_endpoint": summarize(health, 1),
        },
        "process_memory": {
            "rss_before_bytes": rss_before,
            "rss_after_bytes": process.memory_info().rss,
        },
        "all_thresholds_passed": all(
            percentile(values, 0.95) <= threshold
            for values, threshold in (
                (profiling, 60),
                (preview, 5),
                (generation, 60),
                (health, 1),
            )
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["all_thresholds_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
