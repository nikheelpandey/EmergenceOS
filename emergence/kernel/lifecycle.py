"""
kernel/lifecycle.py

Owns Process lifecycle transitions.

The LifecycleManager is the single authority for mutating process
lifecycle state. All transitions are validated against
PROCESS_STATE_TRANSITIONS before being applied.
"""

from __future__ import annotations

from emergence.core.process import Process
from emergence.core.state import ProcessState


class LifecycleManager:
    """
    Responsible for transitioning Process lifecycle states.
    """

    def transition_to(
        self,
        process: Process,
        new_state: ProcessState,
    ) -> None:
        """
        Transition a process to a new lifecycle state.

        Raises
        ------
        ValueError
            If the transition is not allowed.
        """
        process.transition_to(new_state)

    def ready(self, process: Process) -> None:
        """Transition CREATED -> READY."""
        self.transition_to(process, ProcessState.READY)

    def start(self, process: Process) -> None:
        """Transition the process to RUNNING."""
        self.transition_to(process, ProcessState.RUNNING)

    def complete(self, process: Process) -> None:
        """Transition the process to COMPLETED."""
        self.transition_to(process, ProcessState.COMPLETED)

    def fail(
        self,
        process: Process,
        reason: str | None = None,
    ) -> None:
        """Transition the process to FAILED."""
        process.fail(reason)

    def cancel(self, process: Process) -> None:
        """Transition the process to CANCELLED."""
        self.transition_to(process, ProcessState.CANCELLED)

    def wait(self, process: Process) -> None:
        """Transition RUNNING -> WAITING."""
        self.transition_to(process, ProcessState.WAITING)

    def block(self, process: Process) -> None:
        """Transition RUNNING -> BLOCKED."""
        self.transition_to(process, ProcessState.BLOCKED)

    def wake(self, process: Process) -> None:
        """Transition WAITING/BLOCKED -> READY."""
        if process.state == ProcessState.WAITING:
            self.transition_to(process, ProcessState.READY)
        elif process.state == ProcessState.BLOCKED:
            self.transition_to(process, ProcessState.READY)
