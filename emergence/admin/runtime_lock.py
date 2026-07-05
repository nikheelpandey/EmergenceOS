from __future__ import annotations

import os
import signal
from dataclasses import dataclass
from datetime import UTC, datetime

from emergence.admin.paths import (
    RuntimeManifest,
    manifest_path,
    pid_path,
    write_manifest,
)


class RuntimeLockError(Exception):
    pass


@dataclass
class RuntimeLock:
    """
    Ensures only one EmergenceOS runtime owns the admin API per data dir.
    """

    _acquired: bool = False

    @classmethod
    def create(cls) -> RuntimeLock:
        return cls()

    def acquire(self) -> None:
        pid_path().parent.mkdir(parents=True, exist_ok=True)

        if pid_path().exists():
            existing_pid = int(pid_path().read_text().strip())
            if _process_alive(existing_pid):
                raise RuntimeLockError(
                    f"EmergenceOS runtime already running (pid {existing_pid}). "
                    "Stop it before starting a new instance."
                )
            self._cleanup_stale()

        pid_path().write_text(str(os.getpid()) + "\n")
        self._acquired = True

    def publish_manifest(
        self,
        *,
        host: str,
        port: int,
        http_port: int | None = None,
    ) -> None:
        write_manifest(
            RuntimeManifest(
                pid=os.getpid(),
                host=host,
                port=port,
                started_at=datetime.now(UTC).isoformat(),
                http_port=http_port,
            )
        )

    def release(self) -> None:
        if not self._acquired:
            return

        if pid_path().exists():
            try:
                recorded = int(pid_path().read_text().strip())
            except ValueError:
                recorded = -1
            if recorded == os.getpid():
                pid_path().unlink(missing_ok=True)

        if manifest_path().exists():
            manifest_path().unlink(missing_ok=True)

        self._acquired = False

    def _cleanup_stale(self) -> None:
        pid_path().unlink(missing_ok=True)
        if manifest_path().exists():
            manifest_path().unlink(missing_ok=True)


def _process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    else:
        return True


def terminate_runtime_pid(pid: int) -> None:
    """Send SIGTERM to a running runtime process."""
    os.kill(pid, signal.SIGTERM)
