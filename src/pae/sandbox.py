"""Subprocess sandbox with bounded workspace, time, memory, CPU, and output."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import psutil

from pae.persistence.errors import (
    SandboxExecutionFailed,
    SandboxResourceLimit,
    SandboxTimeout,
)


class SandboxRunner:
    def __init__(
        self,
        workspace_root: Path,
        *,
        timeout_seconds: float = 5,
        memory_limit_bytes: int = 256 * 1024 * 1024,
        cpu_limit_seconds: float = 5,
        output_limit_bytes: int = 5 * 1024 * 1024,
    ) -> None:
        self.workspace_root = workspace_root.resolve()
        self.timeout_seconds = timeout_seconds
        self.memory_limit_bytes = memory_limit_bytes
        self.cpu_limit_seconds = cpu_limit_seconds
        self.output_limit_bytes = output_limit_bytes

    @staticmethod
    def _kill_tree(pid: int) -> None:
        try:
            process = psutil.Process(pid)
            children = process.children(recursive=True)
            for child in children:
                child.kill()
            process.kill()
            psutil.wait_procs([*children, process], timeout=2)
        except psutil.Error:
            pass

    async def run(
        self, request: dict[str, Any], *, timeout_seconds: float | None = None
    ) -> dict[str, Any]:
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        workspace = Path(tempfile.mkdtemp(prefix="pae-sandbox-", dir=self.workspace_root))
        request_path = workspace / "request.json"
        output_path = workspace / "output.json"
        core_source = Path(__file__).with_name("runtime_core.py")
        worker = Path(__file__).with_name("sandbox_worker.py")
        try:
            shutil.copyfile(core_source, workspace / "runtime_core.py")
            request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
            environment = {
                "PATH": os.environ.get("PATH", ""),
                "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
                "TEMP": str(workspace),
                "TMP": str(workspace),
                "PYTHONHASHSEED": "0",
                "PYTHONIOENCODING": "utf-8",
                "NO_PROXY": "*",
            }
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-I",
                str(worker),
                str(request_path),
                str(output_path),
                cwd=workspace,
                env=environment,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            started = asyncio.get_running_loop().time()
            try:
                while process.returncode is None:
                    await asyncio.sleep(0.02)
                    elapsed = asyncio.get_running_loop().time() - started
                    try:
                        observed = psutil.Process(process.pid)
                        memory = observed.memory_info().rss + sum(
                            child.memory_info().rss for child in observed.children(recursive=True)
                        )
                        cpu = sum(observed.cpu_times()[:2]) + sum(
                            sum(child.cpu_times()[:2])
                            for child in observed.children(recursive=True)
                        )
                    except psutil.Error:
                        memory = cpu = 0
                    if memory > self.memory_limit_bytes or cpu > self.cpu_limit_seconds:
                        self._kill_tree(process.pid)
                        await process.wait()
                        raise SandboxResourceLimit(
                            "Sandbox resource limit exceeded; execution was terminated."
                        )
                    if (
                        output_path.exists()
                        and output_path.stat().st_size > self.output_limit_bytes
                    ):
                        self._kill_tree(process.pid)
                        await process.wait()
                        raise SandboxResourceLimit(
                            "Sandbox output limit exceeded; execution was terminated."
                        )
                    if elapsed > (timeout_seconds or self.timeout_seconds):
                        self._kill_tree(process.pid)
                        await process.wait()
                        raise SandboxTimeout("Sandbox execution timed out and was terminated.")
                stdout, stderr = await process.communicate()
            except asyncio.CancelledError:
                self._kill_tree(process.pid)
                await process.wait()
                raise
            if process.returncode != 0:
                del stdout, stderr
                raise SandboxExecutionFailed("Sandbox execution failed.")
            if not output_path.exists():
                raise SandboxExecutionFailed("Sandbox did not produce an output result.")
            if output_path.stat().st_size > self.output_limit_bytes:
                raise SandboxResourceLimit("Sandbox output exceeded the configured limit.")
            result = json.loads(output_path.read_text(encoding="utf-8"))
            if not isinstance(result, dict):
                raise SandboxExecutionFailed("Sandbox output was not a JSON object.")
            return result
        finally:
            shutil.rmtree(workspace, ignore_errors=True)
