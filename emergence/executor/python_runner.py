"""
executor/python_runner.py

Executes Python process implementations.
"""

from __future__ import annotations

import importlib

from emergence.core.process import Process
from emergence.executor.runner import Runner


class PythonRunner(Runner):
    """
    Executes Python callables.

    The implementation string should be

        module:function

    Example

        examples.hello_world:run
    """

    def run(self, process: Process):
        implementation = process.definition.implementation

        module_name, function_name = implementation.split(":")

        module = importlib.import_module(module_name)

        function = getattr(module, function_name)

        return function(process)