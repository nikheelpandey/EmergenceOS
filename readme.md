# EmergenceOS

> An operating system for autonomous intelligence.

EmergenceOS is an experimental kernel and runtime for AI agents. Instead of treating an agent as a single program, it runs intelligence as **long-lived, event-driven processes** coordinated by a capability-gated kernel.

**Release:** [v0.2.0](CHANGELOG.md) · **Tests:** 486 passing · **Milestones:** M1–M18 complete

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
| **AI Tools** | `llm.chat` (Ollama/OpenAI/mock), `memory.search` RAG |
| **AI Plugins** | LLM planner, researcher, evaluator, research assistant |
| **Apps** | hello_world, system-model demo, cognitive demo, long-running services, research assistant |

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

# Run the persistent OS (default — runs until Ctrl+C)
python boot.py

# Batch one-shot demos (drain and exit)
python boot.py --once --hello
python boot.py --once --demo
python boot.py --once --goal
python boot.py --once --services

# Persistent OS + spawn work immediately
python boot.py --research "topic"
python boot.py --goal

# Or via eos CLI
./eos serve
```

At the `eos>` prompt you can spawn plugins, run research, and inspect the live system:

```
eos> help
eos> ps
eos> spawn researcher
eos> research "event-driven architecture"
eos> quit
```

Set `EMERGENCE_LLM_PROVIDER=ollama` for real LLM inference (default: `mock`).

### CLI

```bash
./eos ps                    # list processes
./eos sched                 # scheduler view
./eos state                 # state store
./eos budget                # resource usage
./eos trace <correlation_id>
./eos approve <request_id>  # grant pending user approval
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

## Roadmap

M1–M18 delivered the kernel and reference cognitive AI stack. Future work:

| Area | Direction |
|------|-----------|
| Distributed runtime | Multiple kernels, cluster scheduling |
| Advanced memory | Chroma/vector DB backends, knowledge graphs |
| HTTP ingress | User events and approval via REST API |
| Additional runners | Docker, WASM execution backends |

Details in [milestone.md](milestone.md).

---

## Core principles

- **Event-driven** — everything happens because of an observable event
- **Long-lived processes** — sleep, wait, wake, checkpoint, resume
- **Kernel never thinks** — reasoning is a managed resource in plugins
- **Capability security** — least privilege on every gated service
- **Composition** — small processes combine into larger systems

---

## Status

**v0.2.0** — Cognitive AI stack complete (M13–M18). Kernel + LLM tools, RAG, planner, researcher/evaluator, human-in-the-loop, and research assistant ship together.

---

## License

Active development. License to be added in a future release.
