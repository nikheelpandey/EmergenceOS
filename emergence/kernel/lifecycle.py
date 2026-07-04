"""
kernel/lifecycle.py

Owns Process lifecycle transitions.
"""

from __future__ import annotations

from emergence.core.process import Process


class LifecycleManager:
    """
    Responsible for transitioning Process lifecycle states.
    """

    def start(self, process: Process) -> None:
        process.start()

    def complete(self, process: Process) -> None:
        process.complete()

    def fail(
        self,
        process: Process,
        reason: str,
    ) -> None:
        process.fail(reason)