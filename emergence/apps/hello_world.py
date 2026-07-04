"""
examples/hello_world.py
"""

from emergence.core.process import Process


def run(process: Process):

    print()

    print("=" * 50)
    print("EmergenceOS")
    print("Hello from process:", process.definition.name)
    print("=" * 50)
    print()

    return "success"