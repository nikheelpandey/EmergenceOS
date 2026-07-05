"""
examples/hello_world.py
"""

from emergence.core.process_context import ProcessContext


def run(context: ProcessContext):
    print()
    print("=" * 50)
    print("EmergenceOS")
    print("Hello from process:", context.definition.name)
    print("=" * 50)

    result = context.tools.invoke("echo", {"message": "success"})
    print("Tool result:", result.result)
    print()

    return result.result
