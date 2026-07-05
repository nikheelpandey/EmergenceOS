from __future__ import annotations

from abc import ABC, abstractmethod


class WaitCondition(ABC):
    """
    Base class for conditions that block a process.

    A process enters the WAITING state when it is associated with
    a WaitCondition. The Scheduler determines when the condition
    has been satisfied and transitions the process back to READY.
    """

    @abstractmethod
    def is_satisfied(self) -> bool:
        """
        Return True when the process should resume execution.
        """
        raise NotImplementedError