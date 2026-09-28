"""Verified backup and restore for local PAE persistence and artifact storage."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import cast
from zipfile import ZIP_DEFLATED, ZipFile


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def create_backup(
    database_path: Path,
    sample_directory: Path,
    artifact_directory: Path,
    output_path: Path,
) -> dict[str, object]:
    """Create a consistent SQLite snapshot plus bounded application-owned files."""

    if not database_path.is_file():
        raise FileNotFoundError("PAE database does not exist")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    entries: dict[str, bytes] = {}
    with tempfile.TemporaryDirectory(prefix="pae-backup-") as directory:
        snapshot = Path(directory) / "pae.sqlite3"
        source = sqlite3.connect(database_path)
        target = sqlite3.connect(snapshot)
        try:
            source.backup(target)
            target.commit()
        finally:
            target.close()
            source.close()
        entries["database/pae.sqlite3"] = snapshot.read_bytes()
    for prefix, root in (("samples", sample_directory), ("artifacts", artifact_directory)):
        if not root.exists():
            continue
        resolved_root = root.resolve()
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            resolved = path.resolve()
            if resolved_root not in resolved.parents:
                raise ValueError("backup path escaped its configured storage root")
            relative = path.relative_to(root).as_posix()
            entries[f"{prefix}/{relative}"] = path.read_bytes()
    manifest: dict[str, object] = {
        "format_version": "1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "files": [
            {"path": name, "sha256": _sha256(content), "size_bytes": len(content)}
            for name, content in sorted(entries.items())
        ],
        "contains_environment_secrets": False,
    }
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with ZipFile(temporary, "w", ZIP_DEFLATED) as archive:
        for name, content in sorted(entries.items()):
            archive.writestr(name, content)
        archive.writestr("backup-manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    temporary.replace(output_path)
    return manifest


def restore_backup(
    archive_path: Path,
    database_path: Path,
    sample_directory: Path,
    artifact_directory: Path,
) -> dict[str, object]:
    """Verify every entry and restore only into empty application-owned targets."""

    targets = (database_path, sample_directory, artifact_directory)
    if database_path.exists() or any(path.exists() and any(path.iterdir()) for path in targets[1:]):
        raise FileExistsError("restore targets must be empty")
    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        if "backup-manifest.json" not in names:
            raise ValueError("backup manifest is missing")
        manifest = cast(dict[str, object], json.loads(archive.read("backup-manifest.json")))
        file_entries = cast(list[dict[str, object]], manifest["files"])
        expected = {str(item["path"]): item for item in file_entries}
        if set(expected) != names - {"backup-manifest.json"}:
            raise ValueError("backup entries do not match the manifest")
        contents: dict[str, bytes] = {}
        for name, item in expected.items():
            path = PurePosixPath(name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or path.parts[0]
                not in {
                    "database",
                    "samples",
                    "artifacts",
                }
            ):
                raise ValueError("backup contains an unsafe path")
            content = archive.read(name)
            if _sha256(content) != str(item["sha256"]) or len(content) != int(
                str(item["size_bytes"])
            ):
                raise ValueError("backup checksum verification failed")
            contents[name] = content
    for name, content in contents.items():
        path = PurePosixPath(name)
        if path.parts[0] == "database":
            target = database_path
        else:
            root = sample_directory if path.parts[0] == "samples" else artifact_directory
            target = root.joinpath(*path.parts[1:])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    connection = sqlite3.connect(database_path)
    try:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("restored SQLite database failed integrity_check")
    finally:
        connection.close()
    return manifest
