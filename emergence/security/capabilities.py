from __future__ import annotations

from typing import TYPE_CHECKING

from emergence.security.capability import Capability

if TYPE_CHECKING:
    from emergence.core.process_definition import ProcessDefinition

# ==========================================================
# State
# ==========================================================

STATE_READ = Capability(
    "state.read",
    "Read values from the global StateStore.",
)

STATE_WRITE = Capability(
    "state.write",
    "Create, update or delete values in the StateStore.",
)

# ==========================================================
# Memory
# ==========================================================

MEMORY_READ = Capability(
    "memory.read",
    "Read long-term memory.",
)

MEMORY_WRITE = Capability(
    "memory.write",
    "Write long-term memory.",
)

# ==========================================================
# Events
# ==========================================================

EVENT_PUBLISH = Capability(
    "event.publish",
    "Publish events to the EventBus.",
)

EVENT_SUBSCRIBE = Capability(
    "event.subscribe",
    "Subscribe to events from the EventBus.",
)

MESSAGE_SEND = Capability(
    "message.send",
    "Send messages to other processes via the kernel.",
)

# ==========================================================
# Process Management
# ==========================================================

PROCESS_CREATE = Capability(
    "process.create",
    "Create new processes.",
)

PROCESS_TERMINATE = Capability(
    "process.terminate",
    "Terminate running processes.",
)

PROCESS_INSPECT = Capability(
    "process.inspect",
    "Inspect running processes.",
)

# ==========================================================
# Filesystem
# ==========================================================

FILESYSTEM_READ = Capability(
    "filesystem.read",
    "Read from the virtual filesystem.",
)

FILESYSTEM_WRITE = Capability(
    "filesystem.write",
    "Write to the virtual filesystem.",
)

# ==========================================================
# Tool Execution
# ==========================================================

TOOL_PYTHON = Capability(
    "tool.python",
    "Execute Python code.",
)

TOOL_SHELL = Capability(
    "tool.shell",
    "Execute shell commands.",
)

TOOL_BROWSER = Capability(
    "tool.browser",
    "Access web browsers.",
)

TOOL_LLM = Capability(
    "tool.llm",
    "Invoke language models.",
)

TOOL_DATABASE = Capability(
    "tool.database",
    "Access databases.",
)

# ==========================================================
# Kernel
# ==========================================================

KERNEL_ADMIN = Capability(
    "kernel.admin",
    "Full access to kernel services.",
)

# ==========================================================
# Checkpoint
# ==========================================================

CHECKPOINT_CREATE = Capability(
    "checkpoint.create",
    "Create process checkpoints.",
)

CHECKPOINT_RESTORE = Capability(
    "checkpoint.restore",
    "Restore process state from a checkpoint.",
)

# ==========================================================
# Capability Resolution
# ==========================================================

CAPABILITY_BY_NAME: dict[str, Capability] = {
    capability.name: capability
    for capability in (
        STATE_READ,
        STATE_WRITE,
        MEMORY_READ,
        MEMORY_WRITE,
        EVENT_PUBLISH,
        EVENT_SUBSCRIBE,
        MESSAGE_SEND,
        PROCESS_CREATE,
        PROCESS_TERMINATE,
        PROCESS_INSPECT,
        FILESYSTEM_READ,
        FILESYSTEM_WRITE,
        TOOL_PYTHON,
        TOOL_SHELL,
        TOOL_BROWSER,
        TOOL_LLM,
        TOOL_DATABASE,
        KERNEL_ADMIN,
        CHECKPOINT_CREATE,
        CHECKPOINT_RESTORE,
    )
}

DEFAULT_PROCESS_CAPABILITIES: frozenset[Capability] = frozenset({
    STATE_READ,
    STATE_WRITE,
    EVENT_PUBLISH,
    EVENT_SUBSCRIBE,
    MESSAGE_SEND,
})


def capabilities_for_definition(
    definition: ProcessDefinition,
) -> frozenset[Capability]:
    """
    Resolve the capabilities granted to a new process instance.

    Every process receives the default capability set plus any
    additional capabilities declared on its ProcessDefinition.
    """

    granted = set(DEFAULT_PROCESS_CAPABILITIES)

    for permission in definition.required_permissions:
        capability = CAPABILITY_BY_NAME.get(permission)
        if capability is not None:
            granted.add(capability)

    return frozenset(granted)