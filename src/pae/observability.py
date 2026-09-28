"""Low-cardinality application metrics and JSON operational logging."""

from __future__ import annotations

import json
import logging
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from threading import Lock

import httpx


class JsonFormatter(logging.Formatter):
    """Emit structured logs without serializing request bodies or credentials."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for name in ("request_id", "method", "route", "status_code", "duration_ms"):
            value = getattr(record, name, None)
            if value is not None:
                payload[name] = value
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_json_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("pae.requests")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(level.upper())
    logger.propagate = False


class MetricsRegistry:
    """Thread-safe in-process counters suitable for one local MVP replica."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._requests: Counter[tuple[str, str, int]] = Counter()
        self._duration: dict[tuple[str, str], float] = defaultdict(float)
        self._alert_deliveries: Counter[str] = Counter()

    def observe(self, method: str, route: str, status_code: int, duration_seconds: float) -> None:
        with self._lock:
            self._requests[(method, route, status_code)] += 1
            self._duration[(method, route)] += duration_seconds

    def snapshot(self) -> tuple[dict[tuple[str, str, int], int], dict[tuple[str, str], float]]:
        with self._lock:
            return dict(self._requests), dict(self._duration)

    def record_alert_delivery(self, status: str) -> None:
        with self._lock:
            self._alert_deliveries[status] += 1

    def render(self, *, queue_depth: int, process_rss_bytes: int) -> str:
        requests, durations = self.snapshot()
        with self._lock:
            alert_deliveries = dict(self._alert_deliveries)
        lines = [
            "# HELP pae_http_requests_total HTTP requests by route and status.",
            "# TYPE pae_http_requests_total counter",
        ]
        for (method, route, status), count in sorted(requests.items()):
            labels = f'method="{method}",route="{route}",status="{status}"'
            lines.append(f"pae_http_requests_total{{{labels}}} {count}")
        lines.extend(
            [
                "# HELP pae_http_request_duration_seconds_total Accumulated request time.",
                "# TYPE pae_http_request_duration_seconds_total counter",
            ]
        )
        for (method, route), duration in sorted(durations.items()):
            labels = f'method="{method}",route="{route}"'
            lines.append(f"pae_http_request_duration_seconds_total{{{labels}}} {duration:.6f}")
        lines.extend(
            [
                "# HELP pae_alert_delivery_total Alert delivery attempts by result.",
                "# TYPE pae_alert_delivery_total counter",
            ]
        )
        for delivery_status, count in sorted(alert_deliveries.items()):
            lines.append(f'pae_alert_delivery_total{{status="{delivery_status}"}} {count}')
        lines.extend(
            [
                "# HELP pae_job_queue_depth Queued generation jobs.",
                "# TYPE pae_job_queue_depth gauge",
                f"pae_job_queue_depth {queue_depth}",
                "# HELP pae_process_resident_memory_bytes Process resident memory.",
                "# TYPE pae_process_resident_memory_bytes gauge",
                f"pae_process_resident_memory_bytes {process_rss_bytes}",
                "",
            ]
        )
        return "\n".join(lines)


class AlertDispatcher:
    """Deliver bounded, credential-free operational alerts to an HTTPS webhook."""

    def __init__(
        self,
        webhook_url: str | None,
        *,
        timeout_seconds: float,
        cooldown_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._webhook_url = webhook_url
        self._timeout_seconds = timeout_seconds
        self._cooldown_seconds = cooldown_seconds
        self._client = client
        self._lock = Lock()
        self._last_attempt: dict[tuple[str, ...], float] = {}

    async def deliver(self, alerts: list[str], context: dict[str, object]) -> str:
        if not alerts:
            return "not_required"
        if self._webhook_url is None:
            return "disabled"
        fingerprint = tuple(sorted(alerts))
        now = time.monotonic()
        with self._lock:
            previous = self._last_attempt.get(fingerprint)
            if previous is not None and now - previous < self._cooldown_seconds:
                return "throttled"
            self._last_attempt[fingerprint] = now
        payload = {
            "event": "pae.operational_alert",
            "occurred_at": datetime.now(UTC).isoformat(),
            "alerts": list(fingerprint),
            "context": context,
        }
        try:
            if self._client is not None:
                response = await self._client.post(self._webhook_url, json=payload)
            else:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.post(self._webhook_url, json=payload)
            response.raise_for_status()
            return "delivered"
        except httpx.HTTPError:
            return "failed"
