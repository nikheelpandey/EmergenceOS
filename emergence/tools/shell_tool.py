from __future__ import annotations

import subprocess
from typing import Any

from emergence.core.ids import ProcessID


def create_shell_exec_handler():
    def handler(args: dict[str, Any], process_id: ProcessID) -> dict[str, Any]:
        command = str(args.get("command", "")).strip()
        if not command:
            raise ValueError("command required")

        timeout = float(args.get("timeout", 30.0))
        max_output = int(args.get("max_output", 65_536))
        cwd = args.get("cwd")
        shell = bool(args.get("shell", False))

        completed = subprocess.run(
            command if shell else command.split(),
            shell=shell,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        truncated = False
        if len(stdout) > max_output:
            stdout = stdout[:max_output]
            truncated = True
        if len(stderr) > max_output:
            stderr = stderr[:max_output]
            truncated = True

        return {
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "truncated": truncated,
        }

    return handler
