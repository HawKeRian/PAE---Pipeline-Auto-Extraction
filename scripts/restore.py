"""Restore a verified PAE backup into empty paths."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pae.backup import restore_backup


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    args = parser.parse_args()
    manifest = restore_backup(args.archive, args.database, args.samples, args.artifacts)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
