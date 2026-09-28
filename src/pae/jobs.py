"""Bounded persistent worker orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pae.persistence.models import JobView
from pae.persistence.repository import Repository


@dataclass(frozen=True)
class JobExecutionResult:
    result: dict[str, Any]
    validation_result: dict[str, Any]
    validation_passed: bool


class RetryableJobError(RuntimeError):
    """A transient worker failure eligible for bounded retry."""

    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


class JobWorker:
    """Claim and execute at most one persisted job per call."""

    def __init__(
        self,
        repository: Repository,
        *,
        worker_id: str,
        concurrency_limit: int = 1,
    ) -> None:
        self._repository = repository
        self._worker_id = worker_id
        self._concurrency_limit = concurrency_limit

    def run_once(self, handler: Callable[[JobView], JobExecutionResult]) -> JobView | None:
        job = self._repository.claim_next_job(
            self._worker_id, concurrency_limit=self._concurrency_limit
        )
        if job is None:
            return None
        try:
            execution = handler(job)
        except RetryableJobError as exc:
            return self._repository.fail_job(job.job_id, exc.error_code, retryable=True)
        except Exception:
            return self._repository.fail_job(job.job_id, "WORKER_ERROR", retryable=False)
        return self._repository.complete_job(
            job.job_id,
            execution.result,
            execution.validation_result,
            validation_passed=execution.validation_passed,
        )
