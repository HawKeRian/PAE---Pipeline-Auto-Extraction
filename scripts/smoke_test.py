"""Smoke-test a running PAE release without credentials."""

from __future__ import annotations

import argparse
import json
import urllib.request


def fetch(base_url: str, path: str) -> dict[str, object]:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}{path}", timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"{path} returned {response.status}")
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    health = fetch(args.base_url, "/health")
    ready = fetch(args.base_url, "/ready")
    if health.get("status") != "ok" or ready.get("status") != "ready":
        raise RuntimeError("PAE did not pass health/readiness smoke checks")
    print(json.dumps({"health": health, "ready": ready}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
