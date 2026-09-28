"""Deterministic identities used to detect stale specifications and artifacts."""

import hashlib
import json

from pydantic import BaseModel


def model_fingerprint(model: BaseModel) -> str:
    """Return SHA-256 over canonical JSON for an immutable domain model."""

    canonical = json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
