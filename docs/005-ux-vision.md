# 005 - UX Vision

> *"The interface is a window into a living, autonomous system — not a conversation with a single assistant."*

---

# Purpose

This document defines how EmergenceOS should be exposed to end users.

It complements [000-vision.md](000-vision.md) (why we exist), [001-principles.md](001-principles.md) (architectural constraints), and [003-system-model.md](003-system-model.md) (kernel ontology). Those documents describe infrastructure. This document describes **experience**.

If a proposed UI feature treats EmergenceOS as a chatbot, task manager, or workflow builder, it should be rejected or redesigned against this vision.

---

# Positioning

> **EmergenceOS is an operating system for autonomous work. You define goals. The system plans, coordinates, remembers, and executes — and keeps working until the work is complete.**

This captures the architecture without mentioning implementation details like processes, plugins, or capabilities.

---

# The Core Shift

EmergenceOS should not compete with chat-first AI products on their terms. It should establish a new category.

| Traditional AI products | EmergenceOS |
|-------------------------|-------------|
| Revolve around **conversations** | Revolves around **goals, services, events, memory, and knowledge** |
| One assistant thread | Many coordinated workloads |
| Memory is invisible | Knowledge accumulates and is browsable |
| Time is turn-by-turn | Time is a first-class dimension |
| Black box execution | Everything inspectable |

Desktop operating systems revolve around files and applications. EmergenceOS revolves around **Goals, Knowledge, Events, and Spaces** — with Processes visible the way Activity Monitor makes background work legible without asking users to manage them.

---

# First-Class Objects

These are not UI panels. They are the **ontology of the product** — the primitives users reason about.

```
Space
 └── Goal (living workload)
      ├── Processes (visible pipeline)
      ├── Knowledge (accumulated intelligence)
      ├── Timeline (temporal history)
      ├── Events (inspectable audit trail)
      └── Policies (capabilities, approvals, budgets)
```

Six objects map to the user experience. Five exist in kernel form today; Spaces is the primary new primitive.

---

## 1. Space

Eventually users won't have one goal. They'll have hundreds — across different domains of life and work.

```
Personal · Work · Finance · Travel · Health · Startup · Research · Photography
```

Each Space owns:

| Resource | Linux analog |
|----------|-------------|
| Goals | systemd units in a slice |
| Memory / Knowledge | mount namespace + home directory |
| Policies | seccomp / AppArmor profiles |
| Capabilities | user/group permission templates |
| Plugins | installed packages scoped to the space |
| Processes | processes in a cgroup |

### Space desktop

Each Space has a **home view** — not files and folders, but:

- Active goals and their health
- Recent knowledge additions
- Items needing attention (approvals, failures)
- Running process summary

Personal Space and Startup Space look different because the workloads differ. The Space is the user's mental model for "this part of my life."

### Kernel status

**Not built.** Memory is scoped per-process today. StateStore is global. Capabilities are granted per-process at spawn.

**Phase 1:** Space as a UI grouping + memory namespace prefix (`space:category:pid:key`).

**Phase 2:** Policy scoping — capability templates, plugin registration, and budget limits per Space.

---

## 2. Goal — a living workload

A Goal is not a task with a checkbox. It is a **persistent, long-lived workload** — closer to a systemd service than a Jira ticket.

One-shot goals ("write a report on X") and long-running workloads ("Research Assistant") use the **same object shape**. The difference is lifecycle: one completes and archives; the other persists and accumulates.

### Example: living workload card

```
┌─ Research Assistant ────────────────────────────────┐
│  ● Healthy                          Running 12 days │
├─────────────────────────────────────────────────────┤
│  Active goals        12                             │
│  Knowledge           143 MB · 123 docs · 2 reports  │
│  Processes           18 running · 1 waiting         │
│  Attention needed    Approval on "Publish Q2 report"│
├─────────────────────────────────────────────────────┤
│  Planner      ████████░░  done                      │
│  Researcher   ██████████████  running               │
│  Evaluator    ███░░░░░░░░  queued                   │
│  Writer       ██████░░░░  running                   │
│  Publisher    ░░░░░░░░░░  waiting (approval)        │
└─────────────────────────────────────────────────────┘
```

Users submit goals in natural language. The system decomposes, schedules, and reports back. Users never need to `spawn`, `plan`, or `execute` — those are kernel operations, not user operations.

### Goal health is computed, not declared

Health must not be self-reported by plugins or LLMs. The kernel derives it from deterministic signals:

| Signal | Effect on health |
|--------|-----------------|
| Child processes failing | Degraded |
| Budget exceeded (tokens, time) | Degraded |
| Waiting on approval beyond threshold | Needs attention |
| No activity beyond staleness window | Idle |
| All processes healthy, knowledge growing | Healthy |

Health is trustworthy because it comes from infrastructure, not reasoning.

### Kernel status

**Partial.** `CognitiveManager` owns Goal/Plan/Task. Long-running plugins (`research_assistant`, `orchestrator`) demonstrate persistent workloads. Missing: a `GoalRegistry` with aggregate stats (uptime, child count, knowledge size, computed health).

---

## 3. Process — visible, not manageable

> Users never need to **manage** processes. They absolutely understand Downloads, Background sync, Printing, Uploading. Modern operating systems don't hide them. They hide the complexity.

The UI pattern is **Activity Monitor**, not **htop**:

- Show name, state, progress, time running
- Do not show PIDs, runner keys, or spawn commands to default users
- Click to inspect (events, capabilities used, memory written) — not to kill or restart

```
Researcher          Running    ██████████████  2m 14s
Evaluator           Waiting    ░░░░░░░░░░░░░░  —
Publisher           Blocked    ████░░░░░░░░░░  approval needed
```

Most users won't care about individual processes. But they'll subconsciously understand: *multiple things are happening*. That builds trust.

Operator mode exposes management (restart, trace, budget). Default users get visibility without control.

### Kernel status

**Built.** `ProcessTable`, lifecycle states, `BudgetTracker`, `./eos top`. Gap: live kernel connection from observability CLI, and progress semantics tied to goal/task stage rather than raw scheduler frames.

---

## 4. Knowledge — accumulated intelligence

Chat products accumulate context invisibly. EmergenceOS makes intelligence **visible and browsable**.

```
┌─ Knowledge: Research AI OS ────────────────────────┐
│  123 documents · 5 summaries · 14 embeddings       │
│  2 reports · 3 datasets                            │
│  Updated 2 minutes ago                             │
├────────────────────────────────────────────────────┤
│  Q2 Architecture Report        semantic · 2m ago   │
│  Event-driven findings (raw)   episodic · 1h ago   │
│  Token usage analysis          working · 3h ago    │
│  14 indexed chunks             embeddings          │
└────────────────────────────────────────────────────┘
```

### Memory vs Knowledge

| Layer | Role |
|-------|------|
| **Memory** | Kernel primitive — store, retrieve, search; capability-gated; scoped by process |
| **Knowledge** | User-facing aggregation of memory artifacts with types, sizes, provenance, and browse UX |

Knowledge is what Memory becomes when rendered for humans. Every Knowledge item links back to the `MemoryStoredEvent` that created it.

### Kernel status

**Partial.** Memory categories (`WORKING`, `EPISODIC`, `SEMANTIC`), `MemoryStoredEvent`, TF-IDF vector index. Missing: aggregation layer with artifact typing, size accounting, and goal/space scoping.

---

## 5. Timeline — time as a first-class dimension

Operating systems exist over time. Chat does not.

Every Goal has a timeline derived from the event log:

```
Yesterday
  2:14 PM   Planner finished · 3 tasks created
  2:15 PM   Researcher started
  4:30 PM   4 findings stored in knowledge

Today
  9:00 AM   Evaluator requested approval
  9:02 AM   You approved publication
  9:05 AM   Writer started draft revision

Tomorrow (scheduled)
  8:00 AM   Publisher scheduled
```

Timeline entries are **events translated to human language**, grouped by day. Scheduled future items come from cron/scheduler plugins.

This is where the event architecture becomes a UX advantage, not an implementation detail.

### Kernel status

**Built (data layer).** `EventStore` is append-only with timestamps. `ReplayEngine` reconstructs state. Missing: narrative translation layer and UI rendering.

---

## 6. Event — everything inspectable

One of Linux's greatest strengths: everything is observable. EmergenceOS should embrace that.

Clicking any timeline entry or process reveals an inspector:

```
Event: MemoryStored
─────────────────────────────────
When:        2026-07-05 14:17:03
Why:         Researcher completed topic analysis
Process:     researcher (a3f2…)
Plugin:      plugins/researcher/researcher.py
Capability:  memory.write
Duration:    45.2s (process round)
Memory:      +1 episodic entry "findings:event-driven-arch"
Correlation: 8b4c… (trace full chain →)
```

The inspector answers:

- Why did this happen?
- Which process emitted it?
- Which plugin handled it?
- Which capability was used?
- How long did it take?
- What memory changed?

### Kernel status

**Built.** Events carry `source_process`, `event_type`, `timestamp`, `payload`, `correlation_id`. `./eos trace <correlation_id>` renders correlation chains. Missing: live kernel connection and UI drill-down with narrative "why" layer.

---

# Information Architecture

```
EmergenceOS
├── Spaces (sidebar)
│   ├── Personal
│   ├── Work
│   └── Research
│       ├── Space desktop (active goals, knowledge, attention)
│       ├── Goals
│       │   ├── Research AI OS          ← living workload
│       │   │   ├── Overview (health, pipeline, attention)
│       │   │   ├── Knowledge
│       │   │   ├── Timeline
│       │   │   ├── Processes
│       │   │   └── Events
│       │   └── Q2 Report               ← one-shot goal, same shape
│       ├── Knowledge (space-level aggregate)
│       └── Settings (policies, plugins)
└── System (operator mode)
    ├── Activity Monitor (all processes)
    ├── Event log (global)
    ├── Budgets
    └── Traces
```

---

# User Layers

Progressive disclosure across three layers. Default users never leave Layer 1.

## Layer 1 — Goal User (~90%)

- Submit goals in natural language
- See progress as a task pipeline, not a chat log
- Approve or reject with context and preview
- Browse knowledge and timeline
- Receive attention notifications (approval needed, goal failed)

## Layer 2 — Operator

- Activity Monitor across all processes
- Global event log and correlation traces
- Budget and token burn per process
- "Why is this stuck?" diagnostics (WAITING, dependency, approval)
- `./eos ps`, `top`, `sched`, `trace` connected to the **live** kernel

## Layer 3 — Developer

- `eos>` REPL for spawn, plan, research commands
- Plugin development (`plugin.yaml` + Python entrypoint)
- HTTP API / SDK for programmatic control
- Full event payloads and capability debugging

The REPL is operator tooling — like `kubectl exec` or `docker exec`. It is not the primary user interface.

---

# Key UX Patterns

## Goal inbox, not chat history

The home screen is an inbox of goals grouped by Space — not a message thread. Each goal card shows health, pipeline progress, and attention status.

## Approval as a first-class interaction

Sensitive operations pause via `wait_for_approval()`. The UX presents:

- What is being requested
- Preview of the artifact (report, publish action, etc.)
- Approve / Reject / Edit first

Approvals must reach users outside the terminal — push via HTTP ingress, email, Slack, or mobile. Users will not sit at `eos>` waiting.

## Activity feed, not chat transcript

System events translated to human language:

```
2:14 PM  Planning started for "Research report"
2:14 PM  3 tasks created: research → summarize → evaluate
2:15 PM  researcher started (priority 5)
2:17 PM  researcher stored 4 findings in knowledge
2:18 PM  evaluator scored report: 8.2/10
2:18 PM  Waiting for your approval
```

## Empty state teaches the OS metaphor

First launch is not a blank chat. It is:

```
EmergenceOS is running.
No goals yet.

Try: "Research event-driven architecture"
     or install a workload: Research Assistant

Your system has 10 plugins available.
```

This teaches Goals, plugins, and the OS model in one screen.

---

# Entry Points by Persona

| Persona | First touch | Daily use |
|---------|-------------|-----------|
| Curious user | `boot.py --research "topic"` one-shot demo | Web goal inbox |
| Researcher / analyst | "Research X and write a report" | Goal inbox + approvals |
| Operator | `./eos serve` + `./eos top` | Activity Monitor + traces |
| Developer | [building-applications.md](building-applications.md) | REPL + plugin authoring |
| Platform builder | [architecture-diagram.md](architecture-diagram.md) | HTTP API + plugin ecosystem |

One-shot boot flags (`--research`, `--plan`) are onboarding demos. They prove value before asking someone to run a persistent daemon.

---

# What We Are Not Building

| Anti-pattern | Why |
|--------------|-----|
| Single chat window as primary UI | Collapses multi-process coordination into one thread; becomes OpenClaw with extra steps |
| Workflow node graph builder | EmergenceOS schedules via kernel dependencies, not visual DAG editing |
| Task manager with checkboxes | Goals are living workloads, not todos |
| Hidden process execution | Visibility builds trust; management is what's hidden |
| Terminal fluency for basic use | Goal submission must work without `eos>` |
| LLM-reported health/status | Health is computed by the kernel from deterministic signals |

---

# Kernel Mapping

What exists today vs what the UX requires:

| UX primitive | Exists today | Needs building |
|-------------|-------------|----------------|
| Goal (living) | `CognitiveManager`, long-running plugins | `GoalRegistry` with health, uptime, aggregate stats |
| Process (visible) | `ProcessTable`, `./eos top` | Live kernel connection; progress semantics per goal stage |
| Knowledge | Memory categories + `MemoryStoredEvent` | Aggregation layer, artifact typing, space/goal scoping |
| Timeline | `EventStore`, `ReplayEngine` | Event → human narrative translation |
| Inspector | `./eos trace`, event payloads | UI drill-down, correlation chains, "why" narrative |
| Spaces | — | Memory namespace, policy scoping, plugin registration per space |
| Approvals | `wait_for_approval()`, `./eos approve` | Push notifications, preview cards, HTTP ingress |
| Scheduled work | Heartbeat plugin (demonstration) | Cron/scheduling as first-class goal timeline entries |

The event bus is not just infrastructure. It is the **journal** that powers Timeline, Knowledge provenance, and the Inspector.

---

# Implementation Phases

## Phase 1 — Foundation (near term)

- Connect `./eos` observability to the **live** running kernel (not `--demo` spin-ups)
- `GoalRegistry` with computed health, uptime, child process count
- REPL output reformatted as goal pipeline view (not raw text)
- Knowledge aggregation API over memory events (counts, types, last updated)
- Timeline API: filtered event stream with narrative translation

## Phase 2 — Goal Inbox (first product surface)

- HTTP ingress: `POST /goals`, `GET /goals/{id}`, `POST /approvals/{id}`, `GET /events`
- Web UI: Space sidebar, goal cards, pipeline progress, approval cards
- WebSocket stream of translated events per goal
- Activity Monitor view connected to live kernel

## Phase 3 — Spaces

- Space as memory namespace and UI grouping
- Space desktop (active goals, recent knowledge, attention needed)
- Policy templates per Space (default capabilities, approval rules)
- Plugin scoping per Space

## Phase 4 — Channels (optional ingress)

- Slack, email, Telegram as **goal submission channels** — not chat loops
- Message format: "Research X" → creates a goal, replies with tracking link
- Approval pushback to the originating channel

Channels submit goals and receive status updates. They do not host a ReAct loop.

---

# Competitive Boundary

| Product | Category | Primary metaphor |
|---------|----------|-----------------|
| ChatGPT, Claude | Conversational AI | Message thread |
| OpenClaw | Personal AI assistant | Always-on daemon + chat across channels |
| Workflow tools (n8n, etc.) | Automation | Node graph |
| **EmergenceOS** | **OS for autonomous work** | **Goals, Spaces, Knowledge, visible processes** |

OpenClaw wins "assistant in your pocket." EmergenceOS owns **"the computer that does work for you, and shows you exactly what it's doing."**

---

# Relationship to Other Docs

| Document | Relationship |
|----------|-------------|
| [000-vision.md](000-vision.md) | Why — reasoning as a schedulable resource |
| [001-principles.md](001-principles.md) | Constraints — kernel never thinks, everything is a process |
| [003-system-model.md](003-system-model.md) | Ontology — kernel entities this UX renders |
| [004-things-that-cannot-exist.md](004-things-that-cannot-exist.md) | Guardrails — UX must not violate architectural invariants |
| [architecture-diagram.md](architecture-diagram.md) | Implementation — layered system this UX exposes |

---

# Summary

EmergenceOS UX should feel like looking through a window at a **living, autonomous system** — not talking to a single assistant.

Users define goals. The system plans, coordinates, remembers, and executes. Workloads persist. Knowledge accumulates. Processes run visibly in the background. Every action is inspectable. Time matters.

If we fully commit to Goals, Spaces, Knowledge, Events, and visible Processes as first-class objects, the product won't feel like a better chatbot. It will feel like an entirely new category of software — one where the architecture and the experience are the same thing.
