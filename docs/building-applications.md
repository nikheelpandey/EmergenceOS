# Building Applications on EmergenceOS

This guide explains how to create custom applications that run on the EmergenceOS kernel. Applications are **plugins** — installable process modules discovered automatically from the `plugins/` directory.

---

## Quick start

### 1. Create a plugin folder

```
plugins/my_app/
├── plugin.yaml
└── my_app.py
```

### 2. Write `plugin.yaml`

```yaml
name: my_app
version: 1.0.0
description: My first EmergenceOS application.
entrypoint: my_app:run
runner: python
required_capabilities:
  - state.read
  - state.write
  - tool.python
supported_events:
  - process.created
```

| Field | Description |
|-------|-------------|
| `name` | Process definition name used by `kernel.spawn()` |
| `entrypoint` | `module:function` relative to the plugin folder |
| `runner` | Execution backend (`python` today) |
| `required_capabilities` | Permissions granted on spawn (see `emergence/security/capabilities.py`) |
| `max_execution_time_seconds` | Optional budget override for long-running services |

### 3. Implement the entrypoint

Every process receives a `ProcessContext`. Never import kernel singletons — use the context.

```python
from emergence.core.process_context import ProcessContext


def run(context: ProcessContext) -> str:
    context.state.set("greeting", f"hello from {context.definition.name}")
    result = context.tools.invoke("echo", {"message": "success"})
    return str(result.result)
```

### 4. Run it

Plugins in `plugins/` are auto-discovered on boot:

```bash
python boot.py
```

To spawn your app explicitly from code:

```python
from emergence.kernel.boot_context import build_kernel

kernel = build_kernel(spawn="my_app")
kernel.run()
```

---

## ProcessContext API

| Service | Access | Typical use |
|---------|--------|-------------|
| `context.state` | Key-value store | Shared pipeline status, service PIDs |
| `context.memory` | Working / episodic / semantic | Per-process durable state between wakeups |
| `context.mailboxes` | Send / receive messages | Request-response between processes |
| `context.tools` | Invoke registered tools | Side effects via `ToolExecutor` |
| `context.event_bus` | Publish (if capability granted) | Broadcast notifications |
| `context.checkpoints` | Snapshot / restore | Long-running durability |
| `context.wait_for_message()` | Yield to scheduler | Long-lived processes |

### Capabilities

Declare only what you need in `plugin.yaml`. Common capabilities:

- `state.read`, `state.write`
- `memory.read`, `memory.write`
- `message.send`, `message.receive`
- `tool.python`, `tool.invoke`
- `checkpoint.create`, `checkpoint.restore`
- `event.publish`

Unauthorized access raises `PermissionDeniedError`.

---

## Short-lived vs long-running apps

### Short-lived (run once and complete)

Return a value from `run()`. The kernel transitions the process to `COMPLETED`.

```python
def run(context: ProcessContext) -> str:
    context.state.set("result", "done")
    return "done"
```

### Long-running (survive across scheduler rounds)

Persist stage in working memory and end each round with `wait_for_message()`:

```python
from emergence.apps.long_running_runtime import (
    drain_messages,
    get_stage,
    set_stage,
    respond,
)


def run(context: ProcessContext) -> str:
    messages = drain_messages(context)
    stage = get_stage(context)

    if stage == 0:
        # do work...
        set_stage(context, 1)

    context.wait_for_message()  # → WAITING + auto-checkpoint
    return "waiting"
```

See `plugins/heartbeat/` and `plugins/orchestrator/` for full examples.

---

## Messaging between processes

Processes never call each other directly. Use mailboxes:

```python
from emergence.common.request import Request
from emergence.common.response import Response
from emergence.common.notification import Notification

# Request → Response
context.mailboxes.send(
    Request(
        sender_pid=str(context.process_id),
        recipient_pid=other_pid,
        action="ping",
        payload={"round": 1},
    )
)

# Fire-and-forget notification
context.mailboxes.send(
    Notification(
        sender_pid=str(context.process_id),
        recipient_pid=collector_pid,
        topic="job.completed",
        data={"job_id": "abc"},
    )
)
```

Store service PIDs in shared state during boot (see `build_long_running_services()` in `emergence/kernel/boot_context.py`).

---

## Cognitive apps (Goal → Plan → Task)

For multi-step orchestration, use the cognitive API instead of hand-rolling coordination:

```python
from emergence.cognitive.manager import TaskSpec
from emergence.kernel.boot_context import build_kernel

kernel = build_kernel(spawn=None, load_plugins=True)

goal = kernel.create_goal("Research quarterly trends")
kernel.start_planning(goal.goal_id)

plan = kernel.create_plan(
    goal.goal_id,
    [
        TaskSpec("gather", "worker", priority=5),
        TaskSpec("summarize", "worker", dependencies=("gather",), priority=3),
    ],
)
kernel.execute_plan(plan.plan_id)
kernel.run()
```

The kernel schedules tasks as processes. **The kernel never calls an LLM** — decomposition is explicit (`TaskSpec`) or delegated to a planner plugin you provide.

Run the built-in demo:

```bash
python boot.py --goal
```

---

## Boot modes

| Command | Description |
|---------|-------------|
| `python boot.py` | Default `hello_world` plugin |
| `python boot.py --demo` | Coordinator / researcher / evaluator pipeline |
| `python boot.py --goal` | Cognitive Goal → Plan → Tasks demo |
| `python boot.py --services` | Long-running service fleet |

---

## Custom boot wiring

For applications that spawn multiple processes, add a builder in `emergence/kernel/boot_context.py`:

```python
def build_my_app() -> Kernel:
    kernel = build_kernel(spawn=None, load_plugins=True)
    ctx = kernel.context

    worker = kernel.spawn(ctx.registry.get("my_worker"), priority=5)
    ctx.state.set("worker_pid", str(worker.process_id))
    kernel.spawn(ctx.registry.get("my_orchestrator"), priority=10)
    return kernel
```

Then wire it in `boot.py`.

---

## CLI observability

```bash
./eos ps          # process table
./eos sched       # scheduler queue
./eos state       # state store snapshot
./eos budget      # resource usage
./eos trace <id>  # causal event chain
```

---

## Testing your plugin

```python
import pytest
from emergence.kernel.boot_context import build_kernel
from emergence.core.state import ProcessState


@pytest.mark.integration
def test_my_app_completes():
    kernel = build_kernel(spawn="my_app")
    kernel.run()
    assert kernel.context.state.get("greeting") is not None
```

Run the suite:

```bash
pytest
```

---

## Design rules

1. **Everything is a process** — even planners and LLM callers are plugins, not kernel code.
2. **No direct tool access** — use `context.tools.invoke()`.
3. **No hidden state** — persist via `state`, `memory`, or checkpoints.
4. **Events are the audit trail** — every significant action should be observable.
5. **Declare capabilities** — least privilege in `plugin.yaml`.

For architecture background see [001-principles.md](001-principles.md), [003-system-model.md](003-system-model.md), and [milestone.md](../milestone.md).
