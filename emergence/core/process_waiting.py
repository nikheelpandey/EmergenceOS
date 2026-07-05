from __future__ import annotations

from emergence.core.wait_condition import WaitCondition


class ProcessWaiting(Exception):
    """
    Raised by a process to yield execution and enter WAITING.

    The kernel catches this exception, records the wait condition,
    and resumes the process when the condition is satisfied.
    """

    def __init__(self, condition: WaitCondition) -> None:
        self.condition = condition
        super().__init__("Process yielded to scheduler.")
