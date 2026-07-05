# EmergenceOS

> An operating system for autonomous intelligence.

EmergenceOS is an experimental kernel and runtime for AI agents. Instead of treating an agent as a single program, it runs intelligence as **long-lived, event-driven processes** coordinated by a capability-gated kernel.

**Release:** [v0.2.0](CHANGELOG.md) · **Tests:** 486 passing · **Milestones:** M1–M18 complete

---

## What ships in v0.2

| Layer | Components |
|-------|------------|
| **Kernel** | Scheduler, lifecycle, mailboxes, state store, process table, persistent runtime |
| **Security** | Capability-based access control on all gated services |
| **Durability** | Memory manager, checkpoints, event sourcing + replay |
| **Execution** | Executor, Python runner, tool request model |
| **Observability** | Metrics, tracing, audit CLI (`./eos`) |
| **Ingress** | Interactive `eos>` REPL — spawn, plan, research, approve |
| **Plugins** | Auto-discovery from `plugins/` via `plugin.yaml` |
| **Cognitive** | Goal → Plan → Task orchestration API |
| **AI Tools** | `llm.chat` (Ollama/OpenAI/mock), `memory.search` RAG |
| **AI Plugins** | LLM planner, researcher, evaluator, research assistant |
| **Human-in-the-loop** | `wait_for_approval()`, user events, `./eos approve` |
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
python boot.py --once --plan "event-driven architecture"
python boot.py --once --research "emergent systems"

# Persistent OS + spawn work immediately
python boot.py --plan "topic"
python boot.py --research "topic"
python boot.py --goal

# Or via eos CLI
./eos serve
```

At the `eos>` prompt you can spawn plugins, run LLM plans, start research, and inspect the live system:

```
eos> help
eos> ps
eos> spawn researcher
eos> plan "event-driven architecture"
eos> research "emergent systems"
eos> approve <request_id>
eos> quit
```

Set `EMERGENCE_LLM_PROVIDER=ollama` for real LLM inference (default: `mock`).

| Variable | Purpose |
|----------|---------|
| `EMERGENCE_LLM_PROVIDER` | `mock` (default), `ollama`, or `openai` |
| `EMERGENCE_LLM_MODEL` | Model name (provider-specific) |
| `EMERGENCE_LLM_BASE_URL` | API base URL for Ollama/OpenAI-compatible endpoints |
| `EMERGENCE_LLM_API_KEY` | API key for OpenAI-compatible providers |

### CLI

```bash
./eos serve                 # persistent runtime + interactive shell
./eos ps                    # list processes
./eos top                   # live process monitor
./eos sched                 # scheduler view
./eos state                 # state store
./eos budget                # resource usage (tokens, tools, time)
./eos metrics               # system metrics
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

Every process receives a `ProcessContext` with gated access to kernel services. Processes communicate via **mailboxes** (mediated by events), not direct calls. LLM access goes through `context.tools.invoke("llm.chat", …)` — never direct provider imports.

**Full diagrams:** [docs/architecture-diagram.md](docs/architecture-diagram.md) · [architecture.md](architecture.md)

### Project layout

```
EmergenceOS/
├── boot.py                 # Boot entrypoint
├── eos                     # CLI wrapper
├── emergence/              # Kernel and runtime
│   ├── kernel/             # Kernel, lifecycle, mailboxes, boot, ingress, runtime
│   ├── scheduler/          # Priority queue, WAITING/BLOCKED
│   ├── executor/           # Runners and tool executor
│   ├── security/           # Capabilities and gated services
│   ├── memory/             # Working / episodic / semantic memory + vector index
│   ├── checkpoint/         # Process snapshots
│   ├── events/             # Event bus, store, replay
│   ├── cognitive/          # Goal / Plan / Task manager
│   ├── plugins/            # Plugin loader and manager
│   ├── tools/              # LLM providers and tool registry setup
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
python boot.py --once --services
```

---

## Cognitive orchestration

Explicit task decomposition — the kernel schedules; plugins reason:

```python
from emergence.cognitive.manager import TaskSpec

goal = kernel.create_goal("Write technical report")
plan = kernel.create_plan(goal.goal_id, [
    TaskSpec("research", "worker", priority=5),
    TaskSpec("summarize", "worker", dependencies=("research",)),
])
kernel.execute_plan(plan.plan_id)
```

Or delegate decomposition to the LLM planner plugin:

```python
goal = kernel.create_goal("Research event-driven architecture")
kernel.start_planning(goal.goal_id)
kernel.spawn_planner_for_goal(goal.goal_id)
# Planner writes TaskSpec list to state; kernel executes when ready
```

Tasks map to plugin processes. Dependencies feed the scheduler. Decomposition is explicit or delegated to a planner plugin — not built into the kernel.

---

## Human-in-the-loop

Sensitive operations can pause for user approval:

```python
approval = context.wait_for_approval(
    "Publish research report?",
    metadata={"report_id": report_id},
)
if approval.granted:
  # proceed
```

The process checkpoints while waiting. Grant approval from the REPL (`approve <request_id>`) or `./eos approve <request_id>`. The research assistant plugin demonstrates the full flow with `auto_approve` for unattended demos.

---

## Documentation

| Doc | Description |
|-----|-------------|
| [005-ux-vision.md](docs/005-ux-vision.md) | UX vision — Goals, Spaces, Knowledge, and the OS metaphor |
| [architecture-diagram.md](docs/architecture-diagram.md) | Layered architecture with Mermaid diagrams |
| [architecture.md](architecture.md) | Full system architecture reference |
| [building-applications.md](docs/building-applications.md) | Plugin development guide |
| [milestone.md](milestone.md) | Kernel milestone tracker (M1–M18) |
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

**v0.2.0** — Cognitive AI stack complete (M13–M18). LLM tools, RAG memory search, planner/researcher/evaluator plugins, human-in-the-loop approval, interactive ingress REPL, and the research assistant reference app ship together on top of the v0.1 kernel.

---

## License

Active development. License to be added in a future release.
