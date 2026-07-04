"""
executor/runner.py

Defines the Runner abstraction.

A Runner knows how to execute a particular kind of process.

Examples
--------
- PythonRunner
- OllamaRunner
- DockerRunner
- WorkflowRunner
- HumanRunner

The Executor delegates execution to an appropriate Runner.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from emergence.core.process import Process


class Runner(ABC):
    """
    Abstract execution backend.

    A Runner is responsible for executing a Process and
    returning its result.

    The Runner should not:

    - update process state
    - publish events
    - modify the process table
    - schedule other processes

    It performs execution only.
    """

    @abstractmethod
    def run(self, process: Process) -> Any:
        """
        Execute a process.

        Parameters
        ----------
        process:
            The process to execute.

        Returns
        -------
        Any
            The execution result.

        Raises
        ------
        Exception
            Any execution failure should propagate to the caller.
        """
        raise NotImplementedError