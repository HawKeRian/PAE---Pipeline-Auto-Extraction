"""Isolated worker entry point. The parent owns policy, monitoring, and cleanup."""

from __future__ import annotations

import builtins
import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def _blocked(*args: Any, **kwargs: Any) -> None:
    del args, kwargs
    raise PermissionError("operation is disabled inside the PAE sandbox")


def _load_core(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("pae_sandbox_runtime_core", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("sandbox runtime core could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    request_path = Path(sys.argv[1]).resolve()
    output_path = Path(sys.argv[2]).resolve()
    workspace = request_path.parent
    if output_path.parent != workspace:
        raise RuntimeError("sandbox output escaped its workspace")
    request = json.loads(request_path.read_text(encoding="utf-8"))
    core_path = (workspace / "runtime_core.py").resolve()
    core = _load_core(core_path)
    original_open = builtins.open

    def restricted_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        target = Path(file).resolve()
        if target != workspace and workspace not in target.parents:
            raise PermissionError("filesystem access outside the sandbox workspace is disabled")
        return original_open(file, *args, **kwargs)

    builtins.open = restricted_open
    socket.socket = _blocked  # type: ignore[misc,assignment]
    socket.create_connection = _blocked  # type: ignore[assignment]
    subprocess.Popen = _blocked  # type: ignore[misc,assignment]
    subprocess.run = _blocked  # type: ignore[assignment]
    os.system = _blocked  # type: ignore[assignment]
    operation = request.get("operation", "preview")
    result: dict[str, Any]
    if operation == "sleep_probe":
        time.sleep(float(request["seconds"]))
        result = {"probe": "completed"}
    elif operation == "memory_probe":
        size = int(request["bytes"])
        result = {"allocated": len(bytearray(size))}
    elif operation == "network_probe":
        try:
            socket.create_connection(("127.0.0.1", 1))
            result = {"network_blocked": False}
        except PermissionError:
            result = {"network_blocked": True}
    elif operation == "filesystem_probe":
        try:
            original = request["path"]
            with open(original, encoding="utf-8") as handle:
                handle.read(1)
            result = {"filesystem_blocked": False}
        except PermissionError:
            result = {"filesystem_blocked": True}
    elif operation == "process_probe":
        try:
            subprocess.run([sys.executable, "--version"], check=False)
            result = {"process_blocked": False}
        except PermissionError:
            result = {"process_blocked": True}
    elif operation == "crash_probe":
        raise RuntimeError("intentional sandbox crash")
    else:
        result = core.execute(request["specification"], request["rows"])
    output_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
