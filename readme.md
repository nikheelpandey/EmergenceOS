# EmergenceOS

> An operating system for autonomous intelligence.

EmergenceOS is an experimental kernel and runtime for AI agents. Instead of treating an agent as a single program, it runs intelligence as **long-lived, event-driven processes** coordinated by a capability-gated kernel.

**Release:** [v0.1.0](https://github.com/nikheelpandey/EmergenceOS/releases/tag/v0.1.0) · **Tests:** 462 passing · **Milestones:** M1–M12 complete

---

## What ships in v0.1

| Layer | Components |
|-------|------------|
| **Kernel** | Scheduler, lifecycle, mailboxes, state store, process table |
| **Security** | Capability-based access control on all gated services |
| **Durability** | Memory manager, checkpoints, event sourcing + replay |
| **Execution** | Executor, Python runner, tool request model |
| **Observability** | Metrics, tracing, audit CLI (`./eos`) |
| **Plugins** | Auto-discovery from `plugins/` via `plugin.yaml` |
| **Cognitive** | Goal → Plan → Task orchestration API |
| **Apps** | hello_world, system-model demo, cognitive demo, long-running services |

The kernel **never calls an LLM**. Reasoning lives in plugins you install.

---

## Quick start

```bash
# Clone and enter the project
git clone git@github.com:nikheelpandey/EmergenceOS.git
cd EmergenceOS

# Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Run the default hello_world plugin
python boot.py
```

### Boot modes

```bash
python boot.py              # hello_world plugin (default)
python boot.py --demo       # multi-process research pipeline
python boot.py --goal       # Goal → Plan → Tasks cognitive demo
python boot.py --services   # long-running service fleet
```

### CLI

```bash
./eos ps                    # list processes
./eos sched                 # scheduler view
./eos state                 # state store
./eos budget                # resource usage
./eos trace <correlation_id>
```

### Tests

```bash
pytest
```

---

## Architecture

```
                    ┌─────────────────┐
                    │     Kernel      │
                    │ scheduler · bus │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
   Process A           Process B           Process C
   (plugin)            (plugin)            (plugin)
        │                    │                    │
        └──────── mailboxes / events ─────────────┘
                             │
                    state · memory · tools
```

Every process receives a `ProcessContext` with gated access to kernel services. Processes communicate via **mailboxes** (mediated by events), not direct calls.

### Project layout

```
EmergenceOS/
├── boot.py                 # Boot entrypoint
├── eos                     # CLI wrapper
├── emergence/              # Kernel and runtime
│   ├── kernel/             # Kernel, lifecycle, mailboxes, boot
│   ├── scheduler/          # Priority queue, WAITING/BLOCKED
│   ├── executor/           # Runners and tool executor
│   ├── security/           # Capabilities and gated services
│   ├── memory/             # Working / episodic / semantic memory
│   ├── checkpoint/         # Process snapshots
│   ├── events/             # Event bus, store, replay
│   ├── cognitive/          # Goal / Plan / Task manager
│   ├── plugins/            # Plugin loader and manager
│   └── observability/      # Metrics, trace, CLI display
├── plugins/                # Installable applications
├── tests/                  # Unit and integration tests
└── docs/                   # Architecture and guides
```

---

## Build a custom application

Applications are plugins. Drop a folder in `plugins/`:

```
plugins/my_app/
├── plugin.yaml
└── my_app.py
```

```yaml
# plugin.yaml
name: my_app
version: 1.0.0
entrypoint: my_app:run
runner: python
required_capabilities:
  - state.read
  - state.write
```

```python
# my_app.py
from emergence.core.process_context import ProcessContext

def run(context: ProcessContext) -> str:
    context.state.set("status", "running")
    return "ok"
```

**Full guide:** [docs/building-applications.md](docs/building-applications.md)

---

## Long-running processes

Services survive across scheduler rounds by:

1. Persisting stage in **working memory**
2. Ending each round with `context.wait_for_message()` → `WAITING` + auto-checkpoint
3. Waking on `MessageReceivedEvent` → `READY` → re-executed

Reference implementations: `plugins/heartbeat/`, `plugins/orchestrator/`, `emergence/apps/long_running_runtime.py`.

Run the fleet demo:

```bash
python boot.py --services
```

---

## Cognitive orchestration

```python
from emergence.cognitive.manager import TaskSpec

goal = kernel.create_goal("Write technical report")
plan = kernel.create_plan(goal.goal_id, [
    TaskSpec("research", "worker", priority=5),
    TaskSpec("summarize", "worker", dependencies=("research",)),
])
kernel.execute_plan(plan.plan_id)
```

Tasks map to plugin processes. Dependencies feed the scheduler. Decomposition is explicit or delegated to a planner plugin — not built into the kernel.

---

## Documentation

| Doc | Description |
|-----|-------------|
| [building-applications.md](docs/building-applications.md) | Plugin development guide |
| [milestone.md](milestone.md) | Kernel milestone tracker (M1–M12) |
| [CHANGELOG.md](CHANGELOG.md) | Release history |
| [001-principles.md](docs/001-principles.md) | Design principles |
| [003-system-model.md](docs/003-system-model.md) | System model |
| [004-things-that-cannot-exist.md](docs/004-things-that-cannot-exist.md) | Architectural constraints |

---

## Roadmap (cognitive / AI apps)

M1–M12 delivered the kernel. Next milestones target **AI applications that run on this OS**:

| ID | Milestone | Goal |
|----|-----------|------|
| M13 | LLM Tool Provider | Ollama / OpenAI as budgeted tools via `ToolExecutor` |
| M14 | Planner Plugin | LLM-driven Goal → Task decomposition (kernel stays LLM-free) |
| M15 | Memory + RAG | Vector search over episodic/semantic memory |
| M16 | Researcher / Evaluator | Multi-agent research loop with reflection |
| M17 | Human-in-the-loop | `USER_*` events, approval gates, interrupt/resume |
| M18 | Reference AI App | End-to-end Research Assistant on EmergenceOS |

Details in [milestone.md](milestone.md#future-cognitive--ai-milestones).

---

## Core principles

- **Event-driven** — everything happens because of an observable event
- **Long-lived processes** — sleep, wait, wake, checkpoint, resume
- **Kernel never thinks** — reasoning is a managed resource in plugins
- **Capability security** — least privilege on every gated service
- **Composition** — small processes combine into larger systems

---

## Status

**v0.1.0** — First release. Kernel infrastructure is functional; cognitive AI apps are the next focus.

---

## License

Active development. License to be added in a future release.
