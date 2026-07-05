# EmergenceOS

> An operating system for autonomous intelligence.

EmergenceOS is an experimental kernel and runtime for AI agents. Instead of treating an agent as a single program, it runs intelligence as **long-lived, event-driven processes** coordinated by a capability-gated kernel.

**Release:** [v0.3.0](CHANGELOG.md) · **Tests:** 560+ passing · **Milestones:** M1–M29 complete

---

## What ships in v0.3

| Layer | Components |
|-------|------------|
| **Kernel** | Scheduler, lifecycle, mailboxes, state store, process table, persistent runtime |
| **Security** | Capability-based access control on all gated services |
| **Durability** | Event log, SQLite checkpoints, file memory — survives restart (`EMERGENCE_DATA_DIR`) |
| **Control plane** | Live admin API, `./eos serve`, runtime lock |
| **Goals** | `GoalRegistry` — health, uptime, process association, persistent workloads |
| **Knowledge** | Artifact index (findings, reports, docs) with provenance |
| **Timeline** | Event log → human narrative, grouped by day |
| **Inspector** | Full causal chain per event (why, duration, correlation) |
| **HTTP API** | REST + WebSocket on port 8765 — goals, research, approvals |
| **Web UI** | Goal Inbox at `http://127.0.0.1:8765/` — results, timeline, knowledge |
| **Spaces** | Isolated namespaces for work/personal domains |
| **Channels** | Webhook ingress — submit goals from external systems |
| **Cognitive + AI** | Goal → Plan → Task, LLM tools (Ollama/OpenAI/mock), research assistant |

The kernel **never calls an LLM**. Reasoning lives in plugins you install.

---

## Quick start

```bash
git clone git@github.com:nikheelpandey/EmergenceOS.git
cd EmergenceOS

python3 -m venv .venv
source .venv/bin/activate
pip install pytest pytest-cov   # for running tests

# Start the persistent OS (runs until Ctrl+C)
EMERGENCE_DATA_DIR=~/.emergence ./eos serve
```

Open **http://127.0.0.1:8765/** in your browser — the Goal Inbox web UI.

### Research with Ollama (recommended)

```bash
# Terminal 1 — Ollama (if not already running via the macOS app)
ollama pull qwen2.5:7b

# Terminal 2 — EmergenceOS with real LLM
EMERGENCE_LLM_PROVIDER=ollama \
EMERGENCE_LLM_MODEL=qwen2.5:7b \
EMERGENCE_DATA_DIR=~/.emergence \
./eos serve
```

Submit a goal in the web UI (mode: **Research assistant**) or via curl:

```bash
curl -s http://127.0.0.1:8765/goals -X POST \
  -H 'Content-Type: application/json' \
  -d '{"description":"quantum computing","mode":"research"}'
```

View results at `http://127.0.0.1:8765/goals/<goal_id>` or:

```bash
curl -s http://127.0.0.1:8765/goals/<goal_id>/results | python3 -m json.tool
```

### REPL (interactive shell)

With `./eos serve` running, the `eos>` prompt accepts:

```
eos> research quantum computing
eos> report
eos> ps
eos> approve <request_id>
eos> quit
```

### Batch demos (one-shot, no persistence)

```bash
python boot.py --once --hello
python boot.py --once --research "emergent systems"
python boot.py --once --plan "event-driven architecture"
```

---

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `EMERGENCE_DATA_DIR` | `~/.emergence` | Durable storage (events, memory, goals, knowledge) |
| `EMERGENCE_LLM_PROVIDER` | `mock` | `ollama`, `openai`, or `mock` |
| `EMERGENCE_LLM_MODEL` | provider-specific | e.g. `qwen2.5:7b` for Ollama |
| `EMERGENCE_LLM_BASE_URL` | `http://localhost:11434` | Ollama / OpenAI-compatible endpoint |
| `EMERGENCE_LLM_API_KEY` | — | API key for OpenAI-compatible providers |
| `EMERGENCE_HTTP_PORT` | `8765` | HTTP API + web UI port |
| `EMERGENCE_API_TOKEN` | — | Optional bearer token for HTTP API |

---

## CLI

```bash
./eos serve                 # persistent runtime + HTTP + web UI
./eos ps                    # list processes (live kernel)
./eos top                   # live process monitor
./eos sched                 # scheduler view
./eos state                 # state store
./eos budget                # resource usage
./eos trace <correlation_id>
./eos approve <request_id>  # grant pending approval
```

---

## HTTP API

Base URL: `http://127.0.0.1:8765`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Goal Inbox web UI |
| `GET` | `/health` | Health check |
| `GET` | `/goals` | List goals |
| `POST` | `/goals` | Create goal (`{"description":"…","mode":"research"}`) |
| `GET` | `/goals/{id}` | Goal detail |
| `GET` | `/goals/{id}/results` | Report + findings with full content |
| `GET` | `/goals/{id}/timeline` | Narrative timeline |
| `GET` | `/goals/{id}/knowledge` | Knowledge artifacts |
| `GET` | `/events/{id}/inspect` | Event inspector |
| `POST` | `/approvals/{id}` | Grant approval |
| `GET` | `/system/snapshot` | Activity monitor data |
| `POST` | `/channels/webhook` | Channel ingress (`{"text":"Research X"}`) |

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
              state · memory · knowledge · goals
                             │
                    HTTP API · Web UI · CLI
```

Every process receives a `ProcessContext` with gated access to kernel services. LLM access goes through `context.tools.invoke("llm.chat", …)` — never direct provider imports.

**Full diagrams:** [docs/architecture-diagram.md](docs/architecture-diagram.md) · [architecture.md](architecture.md)

### Project layout

```
EmergenceOS/
├── boot.py                 # Boot entrypoint
├── eos                     # CLI wrapper
├── web/                    # Goal Inbox web UI (v0.3)
├── emergence/
│   ├── kernel/             # Kernel, lifecycle, runtime, ingress
│   ├── admin/              # Live control plane TCP API
│   ├── ingress/            # HTTP API, channels, goal submission
│   ├── persistence/        # Durable snapshots and flush
│   ├── cognitive/          # Goal registry, cognitive manager
│   ├── memory/             # Memory manager, knowledge index
│   ├── events/             # Event bus, store, narrative timeline
│   ├── observability/      # Metrics, trace, event inspector
│   ├── spaces/             # Namespace registry
│   ├── scheduler/          # Priority queue + schedule manager
│   └── tools/              # LLM providers
├── plugins/                # Installable applications
├── tests/
└── docs/
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

**Full guide:** [docs/building-applications.md](docs/building-applications.md)

---

## Documentation

| Doc | Description |
|-----|-------------|
| [005-ux-vision.md](docs/005-ux-vision.md) | UX vision — Goals, Spaces, Knowledge |
| [milestone.md](milestone.md) | Milestone tracker (M1–M29, all complete) |
| [architecture-diagram.md](docs/architecture-diagram.md) | Layered architecture diagrams |
| [building-applications.md](docs/building-applications.md) | Plugin development guide |
| [CHANGELOG.md](CHANGELOG.md) | Release history |

---

## Tests

```bash
pytest
```

---

## Status

**v0.3.0** — UX foundation complete (M19–M29). Live control plane, durable persistence, goal registry, knowledge layer, narrative timeline, event inspector, HTTP ingress, Goal Inbox web UI, spaces, scheduled work, and channel ingress. Use the web UI or HTTP API to run research with Ollama — no REPL required.

---

## License

Active development. License to be added in a future release.
